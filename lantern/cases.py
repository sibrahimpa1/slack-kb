"""Questions with the behaviour we expect. Used by the evals, the tests,
the parity check against the browser port, and the demo's suggested questions.

expect: answer (from doc), restricted (exists, not yours), unknown (nothing on it).
visibility: channel / ephemeral / dm.
"""

CASES = [
    # Answers anyone on staff can get
    {"id": "Q-01", "who": "maya", "where": None, "q": "What is the per diem for meals when I travel?", "expect": "answer", "doc": "D-01"},
    {"id": "Q-02", "who": "jonas", "where": "ask-people-ops", "q": "How many weeks of parental leave does the primary caregiver get?", "expect": "answer", "doc": "D-03", "vis": "channel"},
    {"id": "Q-03", "who": "maya", "where": "ask-people-ops", "q": "Can I carry over unused vacation days?", "expect": "answer", "doc": "D-04", "vis": "channel"},
    {"id": "Q-04", "who": "ana", "where": None, "q": "When is pay day in December?", "expect": "answer", "doc": "D-18"},
    {"id": "Q-05", "who": "jonas", "where": None, "q": "What is the hotel cap per night in London?", "expect": "answer", "doc": "D-01"},
    {"id": "Q-06", "who": "maya", "where": None, "q": "How much can I spend on courses and conferences each year?", "expect": "answer", "doc": "D-14"},
    {"id": "Q-07", "who": "ruth", "where": None, "q": "How long do I have to submit receipts for expenses?", "expect": "answer", "doc": "D-01"},
    {"id": "Q-08", "who": "maya", "where": None, "q": "When are engineering promotions decided?", "expect": "answer", "doc": "D-17"},
    {"id": "Q-09", "who": "jonas", "where": None, "q": "Who has to approve an expense over 500 euros?", "expect": "answer", "doc": "D-01"},
    {"id": "Q-10", "who": "leo", "where": None, "q": "How much is the wellbeing allowance for the gym?", "expect": "answer", "doc": "D-14"},
    # Team-only answers
    {"id": "Q-11", "who": "maya", "where": "eng-help", "q": "Can we deploy to production on Friday afternoon?", "expect": "answer", "doc": "D-08", "vis": "channel"},
    {"id": "Q-12", "who": "dev", "where": "eng-help", "q": "How fast do I need to acknowledge a Sev1 page when on call?", "expect": "answer", "doc": "D-07", "vis": "channel"},
    {"id": "Q-13", "who": "maya", "where": "eng-help", "q": "Who gets production access and how often is it renewed?", "expect": "answer", "doc": "D-09", "vis": "ephemeral"},
    {"id": "Q-14", "who": "jonas", "where": "sales-floor", "q": "Who approves a 15% discount on a deal?", "expect": "answer", "doc": "D-10", "vis": "channel"},
    {"id": "Q-15", "who": "dev", "where": None, "q": "When do contractors send invoices?", "expect": "answer", "doc": "D-16"},
    {"id": "Q-16", "who": "dev", "where": None, "q": "Do I get a laptop and is it replaced?", "expect": "answer", "doc": "D-12"},
    # Not yours to read
    {"id": "Q-17", "who": "maya", "where": None, "q": "What is the salary band for an engineer L3?", "expect": "restricted", "doc": "D-05"},
    {"id": "Q-18", "who": "maya", "where": None, "q": "Who approves a discount above 20%?", "expect": "restricted", "doc": "D-10"},
    {"id": "Q-19", "who": "dev", "where": None, "q": "Can contractors get production access through the access gateway?", "expect": "restricted", "doc": "D-09"},
    {"id": "Q-20", "who": "dev", "where": None, "q": "How many weeks of parental leave do we get?", "expect": "answer", "doc": "D-16"},
    # Leadership-only documents that must not even be hinted at
    {"id": "Q-21", "who": "maya", "where": None, "q": "Are the Platform and Data teams going to merge?", "expect": "unknown", "doc": None},
    {"id": "Q-22", "who": "jonas", "where": None, "q": "What was Q3 revenue against plan and what is the runway?", "expect": "unknown", "doc": None},
    {"id": "Q-23", "who": "leo", "where": None, "q": "What was Q3 revenue against plan and what is the runway?", "expect": "answer", "doc": "D-15"},
    {"id": "Q-24", "who": "ruth", "where": None, "q": "What is the salary band for an engineer L3?", "expect": "answer", "doc": "D-05"},
    # Nothing written down
    {"id": "Q-25", "who": "jonas", "where": "ask-people-ops", "q": "Can I bring my dog to the office?", "expect": "unknown", "doc": None, "vis": "channel"},
    {"id": "Q-26", "who": "maya", "where": None, "q": "Is there a company car scheme?", "expect": "unknown", "doc": None},
    {"id": "Q-27", "who": "ana", "where": None, "q": "What is the wifi password for guests?", "expect": "unknown", "doc": None},
    # The answer is fine for the asker, but not for everyone in the channel
    {"id": "Q-28", "who": "ana", "where": "ask-people-ops", "q": "Who approves a discount above 20% or a multi-year price lock?", "expect": "answer", "doc": "D-10", "vis": "ephemeral"},
    {"id": "Q-29", "who": "ruth", "where": "ask-people-ops", "q": "What is the salary band for an account executive?", "expect": "answer", "doc": "D-05", "vis": "ephemeral"},
    # Old policy still in the drive: the current one must win
    {"id": "Q-30", "who": "jonas", "where": None, "q": "What is the daily allowance for meals on business travel?", "expect": "answer", "doc": "D-01"},
]
