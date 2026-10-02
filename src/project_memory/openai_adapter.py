"""Optional live provider. Core contracts do not import this module."""

import os
from time import monotonic
from typing import cast

import httpx2
from openai import APIConnectionError, APIError, APIStatusError, APITimeoutError, OpenAI, omit
from openai.types.responses import ResponseFormatTextConfigParam
from openai.types.shared import ReasoningEffort

from .call_budget import CallBudget
from .language import ModelRequest, ModelResponse
from .models import MemoryError, canonical


class OpenAIModel:
    """OpenAI SDK Responses transport; provider is explicitly bound in the run budget.

    DeepSeek ignores several OpenAI controls, so those fields are not sent and
    no storage/truncation guarantee is inferred from OpenAI compatibility.
    """

    def __init__(
        self,
        budget: CallBudget,
        *,
        api_key: str | None = None,
        transport: httpx2.BaseTransport | None = None,
        strict_schema: bool = False,
    ):
        provider = budget.limits.provider
        if type(strict_schema) is not bool or (strict_schema and provider != "openai"):
            raise MemoryError("strict decoding requires an explicitly supported OpenAI provider")
        self.strict_schema = strict_schema
        env_name, endpoint = {
            "openai": ("PROJECT_MEMORY_OPENAI_API_KEY", "https://api.openai.com/v1"),
            "deepseek": ("PROJECT_MEMORY_DEEPSEEK_API_KEY", "https://api.deepseek.com"),
        }[provider]
        key = api_key if api_key is not None else os.environ.get(env_name)
        if not key or not key.strip():
            raise MemoryError(f"{env_name} is not configured")
        self.budget = budget
        timeout = httpx2.Timeout(budget.limits.timeout_seconds, connect=10.0)
        self.client = OpenAI(
            api_key=key,
            base_url=endpoint,
            organization="",
            project="",
            max_retries=0,
            timeout=timeout,
            http_client=httpx2.Client(
                transport=transport, timeout=timeout, trust_env=False, follow_redirects=False
            ),
        )

    def close(self) -> None:
        self.client.close()

    def complete(self, request: ModelRequest) -> ModelResponse:
        output_format: dict = {"type": "json_object"}
        schema_tag = ""
        if self.strict_schema:
            from .output_schema import EFFECT_VERSION, schema_for

            output_format = {"type": "json_schema", "name": "project_memory",
                             "strict": True, "schema": schema_for(request)}
            schema_tag = (":strict-schema-v2" if request.version == EFFECT_VERSION
                          else ":strict-schema-v1")
        call_id = self.budget.reserve(
            request, extra_input_chars=len(canonical(output_format)) if self.strict_schema else 0,
        )
        started = monotonic()
        outcome, code, output = "error", "unknown", ""
        response_id = None
        model = self.budget.limits.model
        tokens_in, tokens_out, reasoning, known = 0, 0, 0, False
        cached = None
        is_openai = self.budget.limits.provider == "openai"
        effort = self.budget.limits.reasoning_effort
        try:
            response = self.client.responses.create(
                model=model,
                # JSON-mode admission checks inspect input messages, not the separate
                # instructions field. Keep instructions authoritative and evidence user data.
                input=[
                    {"role": "system", "content": request.instructions},
                    {"role": "user", "content": request.payload_json},
                ],
                max_output_tokens=request.max_output_tokens,
                text={"format": cast(ResponseFormatTextConfigParam, output_format)},
                reasoning={"effort": cast(ReasoningEffort, effort)} if effort is not None else omit,
                store=False if is_openai else omit,
                background=False if is_openai else omit,
                stream=False,
                truncation="disabled" if is_openai else omit,
                tools=[],
                tool_choice="none",
                service_tier="default" if is_openai else omit,
            )
            response_id, model = response.id, response.model
            usage = response.usage
            if usage is not None:
                tokens_in, tokens_out = usage.input_tokens, usage.output_tokens
                known = all(type(v) is int and v >= 0 for v in (tokens_in, tokens_out))
                if not known:
                    tokens_in, tokens_out = 0, 0
                elif usage.output_tokens_details is not None:
                    reasoning = usage.output_tokens_details.reasoning_tokens
                if known and usage.input_tokens_details is not None:
                    value = usage.input_tokens_details.cached_tokens
                    if type(value) is int and 0 <= value <= tokens_in:
                        cached = value
            output = response.output_text
            refused = any(
                item.type == "message" and any(block.type == "refusal" for block in item.content)
                for item in response.output
            )
            if len(output) > self.budget.limits.max_response_chars:
                code, output = "response_size_exceeded", ""
            elif response.status == "incomplete":
                outcome, code = "truncated", "incomplete"
            elif refused:
                outcome, code = "refused", "refusal"
            elif response.status != "completed":
                code = "provider_not_completed"
            elif not known:
                code = "missing_or_invalid_usage"
            elif tokens_out > request.max_output_tokens:
                code = "output_token_limit_exceeded"
            elif not output.strip():
                code = "empty_output"
            else:
                outcome, code = "completed", "completed"
        except APITimeoutError:
            code = "timeout"
        except APIStatusError as exc:
            code = f"http_{exc.status_code}"
        except APIConnectionError:
            code = "connection_error"
        except APIError:
            code = "sdk_error"
        except (ValueError, TypeError, AttributeError):
            code, output = "invalid_provider_response", ""
        elapsed = round((monotonic() - started) * 1000, 3)
        self.budget.finish(
            call_id,
            {
                "outcome": outcome,
                "error_code": code,
                "elapsed_ms": elapsed,
                "response_id": response_id,
                "model": model,
                "requested_model": self.budget.limits.model,
                "provider": self.budget.limits.provider,
                "reasoning_effort": effort,
                "usage_known": known,
                "input_tokens": tokens_in if known else None,
                "output_tokens": tokens_out if known else None,
                "reasoning_tokens": reasoning if known else None,
                "cached_input_tokens": cached,
                "response_format": output_format,
            },
        )
        return ModelResponse(
            request.hash,
            f"{self.budget.limits.provider}-responses-v2"
            + schema_tag
            + (f":reasoning-{effort}" if effort is not None else ""),
            model,
            output,
            outcome,
            tokens_in,
            tokens_out,
        )
