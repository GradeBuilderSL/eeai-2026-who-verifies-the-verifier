"""Injected qualifier-drop seed set (20 cases, 4 per corruption family), gold by construction.

Each original is written as segments; segments flagged with a `kind` are restriction spans.
`critical` marks the span whose removal makes `false_claim` appear supported. The corrupted
intermediate = original minus the critical span (the family's operator). Decoy spans exist so
that a minimal-edit search is not trivial. Claims are stated relative to `as_of`.
Author: Claude, 2026-09-21. Self-authored -> adversarial-authoring bias is a known limit; the
operator and gold are mechanical, the scenarios are not.
"""
import json
from pathlib import Path

OUT = Path(__file__).parent / "seed-qualifier-drop.json"


def seg(text, kind=None, critical=False):
    return {"text": text, "kind": kind, "critical": critical}


CASES = [
    dict(id="int-01", family="interval_dropped", domain="retail offer", as_of="2026-09-15",
         segments=[seg("Nordvik Bikes offers a 20% discount on all city bikes "), seg("for customers who order online", "scope"),
                   seg(" "), seg("until 31 August 2026", "temporal", True), seg(". The discount is applied automatically at checkout.")],
         false_claim="Nordvik Bikes offers a 20% discount on all city bikes for customers who order online.",
         true_claim="Nordvik Bikes' 20% online discount on city bikes ended on 31 August 2026."),
    dict(id="int-02", family="interval_dropped", domain="parking rules", as_of="2026-12-10",
         segments=[seg("Parking on Harbour Street is free "), seg("between 1 June and 30 September", "temporal", True),
                   seg(" "), seg("for residents with a permit", "scope"), seg(". Outside that period the standard tariff of 2 EUR per hour applies.")],
         false_claim="Parking on Harbour Street is free for residents with a permit.",
         true_claim="In December, residents with a permit pay the standard tariff of 2 EUR per hour to park on Harbour Street."),
    dict(id="int-03", family="interval_dropped", domain="subscription", as_of="2026-10-01",
         segments=[seg("The introductory price of the Pro plan is 9 EUR per month "), seg("for the first three months", "temporal", True),
                   seg(" "), seg("for new subscribers", "scope"), seg("; afterwards the regular price of 19 EUR per month applies.")],
         false_claim="Pro plan subscribers who joined in April 2026 pay 9 EUR per month.",
         true_claim="Pro plan subscribers who joined in April 2026 now pay the regular price of 19 EUR per month."),
    dict(id="int-04", family="interval_dropped", domain="warranty", as_of="2027-03-01",
         segments=[seg("Every Kestrel espresso machine comes with a free repair warranty "), seg("valid for 24 months from the date of purchase", "temporal", True),
                   seg(". Accidental damage is "), seg("not", "negation"), seg(" covered.")],
         false_claim="A Kestrel espresso machine bought in January 2025 is covered by the free repair warranty.",
         true_claim="A Kestrel espresso machine bought in January 2025 is no longer covered by the free repair warranty."),
    dict(id="era-01", family="eras_merged", domain="pricing", as_of="2026-09-21",
         segments=[seg("From 1 January 2026 the monthly fee for the Basic tariff was 29 EUR. "),
                   seg("From 1 September 2026 the monthly fee for the Basic tariff is 39 EUR.", "era", True),
                   seg(" Existing customers were notified by e-mail "), seg("on 20 August 2026", "temporal"), seg(".")],
         false_claim="The monthly fee for the Basic tariff is 29 EUR.",
         true_claim="The monthly fee for the Basic tariff is 39 EUR."),
    dict(id="era-02", family="eras_merged", domain="tax threshold", as_of="2026-11-05",
         segments=[seg("Until 30 June 2026 the VAT registration threshold was 85,000 EUR of annual turnover. "),
                   seg("Since 1 July 2026 the threshold is 100,000 EUR.", "era", True),
                   seg(" Businesses below the threshold may register "), seg("voluntarily", "scope"), seg(".")],
         false_claim="The VAT registration threshold is 85,000 EUR of annual turnover.",
         true_claim="The VAT registration threshold is 100,000 EUR of annual turnover."),
    dict(id="era-03", family="eras_merged", domain="opening hours", as_of="2026-10-12",
         segments=[seg("During the summer season the museum was open daily from 9:00 to 20:00. "),
                   seg("From 1 October 2026 the museum is open from 10:00 to 17:00 and closed on Mondays.", "era", True),
                   seg(" Tickets are sold "), seg("until one hour before closing", "temporal"), seg(".")],
         false_claim="The museum is open daily from 9:00 to 20:00.",
         true_claim="The museum is open from 10:00 to 17:00 and closed on Mondays."),
    dict(id="era-04", family="eras_merged", domain="shipping", as_of="2026-09-30",
         segments=[seg("In the first half of 2026 standard delivery took 5 working days. "),
                   seg("Since 1 August 2026 standard delivery takes 3 working days.", "era", True),
                   seg(" Express delivery remains 1 working day "), seg("for orders placed before noon", "scope"), seg(".")],
         false_claim="Standard delivery takes 5 working days.",
         true_claim="Standard delivery takes 3 working days."),
    dict(id="can-01", family="cancelled_kept", domain="HR policy", as_of="2026-09-01",
         segments=[seg("On 1 March 2026 the company introduced a mandatory three-days-in-office rule "), seg("for all staff", "scope"),
                   seg(". "), seg("The rule was withdrawn on 15 June 2026 after the works council objected.", "cancellation", True),
                   seg(" Team leads may still agree local arrangements.")],
         false_claim="A mandatory three-days-in-office rule is in force for all staff.",
         true_claim="The mandatory three-days-in-office rule was withdrawn on 15 June 2026."),
    dict(id="can-02", family="cancelled_kept", domain="promotion", as_of="2026-08-20",
         segments=[seg("Sunbird Travel announced a 'kids fly free' promotion on 2 May 2026 "), seg("for bookings made through its own website", "scope"),
                   seg(". "), seg("The promotion was cancelled on 9 June 2026 because of fraud.", "cancellation", True),
                   seg(" Bookings already confirmed were honoured.")],
         false_claim="Sunbird Travel's 'kids fly free' promotion is available for bookings made through its website.",
         true_claim="Sunbird Travel cancelled its 'kids fly free' promotion on 9 June 2026."),
    dict(id="can-03", family="cancelled_kept", domain="regulation", as_of="2026-10-01",
         segments=[seg("A municipal by-law of 10 February 2026 banned short-term rentals "), seg("in the old town", "scope"), seg(". "),
                   seg("The ban was annulled by the regional court on 30 July 2026.", "cancellation", True),
                   seg(" The city has said it may draft a new by-law.")],
         false_claim="Short-term rentals are banned in the old town.",
         true_claim="The old-town short-term rental ban was annulled by the regional court on 30 July 2026."),
    dict(id="can-04", family="cancelled_kept", domain="subsidy", as_of="2026-12-01",
         segments=[seg("The heat-pump subsidy of 3,000 EUR "), seg("for owner-occupied homes", "scope"), seg(" was launched on 1 April 2026. "),
                   seg("The subsidy programme was closed to new applications on 31 October 2026 when the budget was exhausted.", "cancellation", True),
                   seg(" Applications received earlier are still being processed.")],
         false_claim="Owner-occupiers can apply for a 3,000 EUR heat-pump subsidy.",
         true_claim="The heat-pump subsidy programme was closed to new applications on 31 October 2026."),
    dict(id="rec-01", family="recorded_as_valid", domain="regulation", as_of="2026-03-20",
         segments=[seg("The new packaging regulation was published in the official journal on 12 March 2026 "),
                   seg("and enters into force on 1 April 2026", "effective", True), seg(". It applies to "), seg("producers placing more than 10 tonnes on the market per year", "scope"), seg(".")],
         false_claim="The new packaging regulation is in force.",
         true_claim="The new packaging regulation enters into force on 1 April 2026."),
    dict(id="rec-02", family="recorded_as_valid", domain="pricing", as_of="2026-09-25",
         segments=[seg("On 20 August 2026 the board approved a price increase for the Premium tariff from 49 to 59 EUR, "),
                   seg("effective for invoices issued from 1 October 2026", "effective", True), seg(". Customers were informed "), seg("on 1 September", "temporal"), seg(".")],
         false_claim="Premium tariff invoices are charged at 59 EUR.",
         true_claim="The Premium tariff price of 59 EUR applies to invoices issued from 1 October 2026."),
    dict(id="rec-03", family="recorded_as_valid", domain="HR policy", as_of="2026-06-10",
         segments=[seg("The updated travel policy was signed by the CEO on 2 June 2026 "),
                   seg("and applies to trips starting on or after 1 July 2026", "effective", True), seg(". Under the new policy economy class is mandatory "), seg("for flights under six hours", "scope"), seg(".")],
         false_claim="Under the company's travel policy, economy class is mandatory for flights under six hours.",
         true_claim="The updated travel policy applies to trips starting on or after 1 July 2026."),
    dict(id="rec-04", family="recorded_as_valid", domain="tax", as_of="2026-12-15",
         segments=[seg("The reduced VAT rate of 7% for restaurant meals was enacted on 5 November 2026 "),
                   seg("and takes effect on 1 January 2027", "effective", True), seg(". Beverages are "), seg("not", "negation"), seg(" included.")],
         false_claim="Restaurant meals are taxed at the reduced 7% VAT rate.",
         true_claim="The reduced 7% VAT rate for restaurant meals takes effect on 1 January 2027."),
    dict(id="cur-01", family="cursor_ignored", domain="tax threshold", as_of="2026-06-15",
         segments=[seg("The tax-free allowance is set at 12,000 EUR "), seg("from 1 January 2027; until then it remains 11,000 EUR", "cursor", True),
                   seg(". The allowance is granted "), seg("only to residents", "scope"), seg(".")],
         false_claim="The tax-free allowance is 12,000 EUR.",
         true_claim="The tax-free allowance is 11,000 EUR."),
    dict(id="cur-02", family="cursor_ignored", domain="minimum wage", as_of="2026-09-01",
         segments=[seg("The minimum hourly wage is set at 13.50 EUR "), seg("from 1 January 2027; until then it is 12.80 EUR", "cursor", True),
                   seg(". Trainees "), seg("under 18", "scope"), seg(" are exempt.")],
         false_claim="The minimum hourly wage is 13.50 EUR.",
         true_claim="The minimum hourly wage is 12.80 EUR."),
    dict(id="cur-03", family="cursor_ignored", domain="delivery fee", as_of="2026-10-20",
         segments=[seg("Free delivery applies to orders above 30 EUR "), seg("from 1 December 2026; until then the threshold is 50 EUR", "cursor", True),
                   seg(". Bulky items are "), seg("not", "negation"), seg(" eligible.")],
         false_claim="Free delivery applies to orders above 30 EUR.",
         true_claim="Free delivery applies to orders above 50 EUR."),
    dict(id="cur-04", family="cursor_ignored", domain="data retention", as_of="2026-11-10",
         segments=[seg("Customer support logs are retained for 12 months "), seg("under the policy revision taking effect on 1 February 2027; the current policy, in force since 1 May 2026, retains them for 24 months", "cursor", True),
                   seg(". Logs "), seg("older than the retention period", "scope"), seg(" are deleted automatically.")],
         false_claim="Customer support logs are retained for 12 months.",
         true_claim="Customer support logs are retained for 24 months."),
]


def build() -> list[dict]:
    out = []
    for c in CASES:
        original = "".join(s["text"] for s in c["segments"])
        corrupted = "".join(s["text"] for s in c["segments"] if not s["critical"])
        corrupted = corrupted.replace(" .", ".").replace("  ", " ").replace(" ;", ";").replace(";.", ".").strip()
        spans = [dict(index=i, kind=s["kind"], text=s["text"], critical=s["critical"]) for i, s in enumerate(c["segments"]) if s["kind"]]
        assert sum(1 for s in spans if s["critical"]) == 1, c["id"]
        out.append({**{k: v for k, v in c.items() if k != "segments"}, "original": original, "corrupted": corrupted,
                    "spans": spans, "segments": c["segments"],
                    "gold": {"false_claim_vs_original": "unsupported", "true_claim_vs_original": "supported",
                             "false_claim_vs_corrupted_by_construction": "appears_supported"}})
    return out


if __name__ == "__main__":
    cases = build()
    OUT.write_text(json.dumps(cases, indent=2, ensure_ascii=False))
    for c in cases[:2]:
        print(c["id"], "\n ORIGINAL:", c["original"], "\n CORRUPTED:", c["corrupted"], "\n FALSE:", c["false_claim"])
    print(len(cases), "cases ->", OUT.name)
