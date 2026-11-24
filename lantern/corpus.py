"""Synthetic company knowledge for the demo: Fernhill, a 140-person logistics
software company. Everything here is invented. Documents come from three
mocked sources (Confluence, Google Drive, Notion), each with its own sharing
model, which the connectors map to directory groups.
"""

NOW = "2026-11-24"

COMPANY = "Fernhill"

GROUPS = {
    "all_staff": "All employees",
    "contractors": "Contractors",
    "eng": "Engineering",
    "sales": "Sales",
    "people_ops": "People Ops",
    "finance": "Finance",
    "managers": "People managers",
    "leadership": "Leadership team",
}

USERS = {
    "maya": {"name": "Maya Okafor", "title": "Backend engineer", "groups": ["all_staff", "eng"], "slack": "U01MAYA"},
    "jonas": {"name": "Jonas Weber", "title": "Account executive", "groups": ["all_staff", "sales"], "slack": "U02JONAS"},
    "ruth": {"name": "Ruth Lindqvist", "title": "Head of People Ops", "groups": ["all_staff", "people_ops", "managers"], "slack": "U03RUTH"},
    "dev": {"name": "Dev Sharma", "title": "Contract frontend developer", "groups": ["contractors"], "slack": "U04DEV"},
    "ana": {"name": "Ana Costa", "title": "Finance lead", "groups": ["all_staff", "finance", "managers"], "slack": "U05ANA"},
    "leo": {"name": "Leo Brandt", "title": "CEO", "groups": ["all_staff", "managers", "leadership"], "slack": "U06LEO"},
}

# Who the knowledge admins are (can change settings, see the audit log).
ADMINS = ["ruth", "leo"]

# Channels the bot is in. Members decide what may be said in the open.
CHANNELS = {
    "ask-people-ops": {"members": ["maya", "jonas", "ruth", "ana", "leo"], "topic": "Questions about leave, pay days, benefits and policies"},
    "eng-help": {"members": ["maya", "dev"], "topic": "Engineering questions, deploys, on-call"},
    "sales-floor": {"members": ["jonas", "ana", "leo"], "topic": "Deals, pricing and discount approvals"},
}

SOURCES = {
    "confluence": {"name": "Confluence", "scope": "Spaces HR, ENG, SALES"},
    "drive": {"name": "Google Drive", "scope": "Shared drives Finance, People, Leadership"},
    "notion": {"name": "Notion", "scope": "Workspace Company handbook"},
}

DOCS = [
    {
        "id": "D-01", "title": "Travel and expenses policy 2026", "source": "drive", "path": "Finance / Policies",
        "owner": "ana", "groups": ["all_staff"], "discoverable": True, "updated": "2026-01-12", "review_by": "2027-01-12",
        "sections": [
            ("Per diem and hotels", "The daily allowance for meals on business travel is EUR 55 per day. Hotels are capped at EUR 160 per night, or EUR 220 per night in London, Paris and Zurich. Book through the travel desk so the rate is applied automatically."),
            ("Receipts and claims", "Submit every expense with a receipt in the expense app within 30 days of the cost. Claims older than 90 days are not reimbursed. Reimbursements are paid with the next payroll run."),
            ("Approvals", "Any single expense over EUR 500 needs your manager's approval before you spend it. Flights over EUR 900 also need approval from Finance."),
        ],
    },
    {
        "id": "D-02", "title": "Travel policy 2024", "source": "drive", "path": "Finance / Policies / Archive",
        "owner": "ana", "groups": ["all_staff"], "discoverable": True, "updated": "2024-02-03", "review_by": "2025-02-03",
        "superseded_by": "D-01",
        "sections": [
            ("Per diem and hotels", "The daily allowance for meals on business travel is EUR 45 per day. Hotels are capped at EUR 130 per night."),
            ("Receipts", "Submit expenses with receipts within 60 days."),
        ],
    },
    {
        "id": "D-03", "title": "Parental leave", "source": "confluence", "path": "HR / Leave",
        "owner": "ruth", "groups": ["all_staff"], "discoverable": True, "updated": "2026-03-02", "review_by": "2027-03-02",
        "sections": [
            ("How much leave", "The primary caregiver gets 20 weeks of parental leave at full pay. The secondary caregiver gets 6 weeks at full pay. Both can be taken in up to three blocks within 18 months of the birth or adoption."),
            ("How to request it", "Tell People Ops at least 8 weeks before the leave starts. Your manager plans cover with you; you do not need to find cover yourself."),
        ],
    },
    {
        "id": "D-04", "title": "Time off and public holidays", "source": "notion", "path": "Company handbook / Time off",
        "owner": "ruth", "groups": ["all_staff"], "discoverable": True, "updated": "2025-09-18", "review_by": "2026-09-18",
        "sections": [
            ("Annual leave", "Everyone gets 25 days of paid annual leave plus the public holidays of their country of employment. Up to 5 unused days carry over and must be used by 31 March."),
            ("Booking time off", "Request leave in the HR portal at least two weeks ahead for anything longer than three days. Sick days do not count against annual leave; tell your manager before 10:00 on the day."),
        ],
    },
    {
        "id": "D-05", "title": "Salary bands 2026", "source": "drive", "path": "People / Compensation",
        "owner": "ruth", "groups": ["people_ops", "leadership"], "discoverable": True, "updated": "2026-02-01", "review_by": "2027-02-01",
        "canary": "EUR 64,000",
        "sections": [
            ("Engineering bands", "Engineer L2 is EUR 52,000 to EUR 63,000. Engineer L3 is EUR 64,000 to EUR 78,000. Senior engineer L4 is EUR 79,000 to EUR 96,000."),
            ("Sales bands", "Account executive base salary is EUR 48,000 to EUR 60,000 with on-target earnings up to EUR 95,000."),
        ],
    },
    {
        "id": "D-06", "title": "Q1 organisation changes (draft)", "source": "drive", "path": "Leadership / Planning",
        "owner": "leo", "groups": ["leadership"], "discoverable": False, "updated": "2026-11-10", "review_by": "2026-12-15",
        "canary": "merge the Platform and Data teams",
        "sections": [
            ("Proposal", "We plan to merge the Platform and Data teams under one director from 1 February and close the Lisbon office lease when it ends in June."),
        ],
    },
    {
        "id": "D-07", "title": "On-call runbook", "source": "confluence", "path": "ENG / Operations",
        "owner": "maya", "groups": ["eng", "contractors"], "discoverable": True, "updated": "2026-10-05", "review_by": "2027-04-05",
        "sections": [
            ("Severity levels", "Sev1 means customers cannot ship or track parcels; page the on-call engineer and acknowledge within 5 minutes. Sev2 means a degraded feature; acknowledge within 30 minutes. Sev3 waits for working hours."),
            ("During an incident", "The first responder becomes incident commander until they hand over. Open a channel named inc-date-topic, post updates every 30 minutes for a Sev1, and write the postmortem within 5 working days."),
        ],
    },
    {
        "id": "D-08", "title": "How we deploy", "source": "confluence", "path": "ENG / Delivery",
        "owner": "maya", "groups": ["eng", "contractors"], "discoverable": True, "updated": "2026-06-20", "review_by": "2026-12-20",
        "sections": [
            ("Reviews", "Every change to main needs two approving reviews, one of them from a code owner. CI must be green before merge."),
            ("Deploy windows", "Production deploys run Monday to Thursday until 16:00 and on Friday until 14:00. There is a deploy freeze from 20 December to 3 January."),
        ],
    },
    {
        "id": "D-09", "title": "Production access", "source": "confluence", "path": "ENG / Security",
        "owner": "maya", "groups": ["eng"], "discoverable": True, "updated": "2026-05-14", "review_by": "2026-11-14",
        "sections": [
            ("Who gets access", "Employees on the engineering on-call rota get production access through the access gateway, approved by their lead and renewed every 90 days. Contractors never get standing production access."),
            ("Break-glass", "In a Sev1, the incident commander can grant 4 hours of break-glass access; it is logged and reviewed the next day."),
        ],
    },
    {
        "id": "D-10", "title": "Discount approval matrix", "source": "confluence", "path": "SALES / Deal desk",
        "owner": "ana", "groups": ["sales", "finance", "leadership"], "discoverable": True, "updated": "2026-07-01", "review_by": "2027-01-01",
        "sections": [
            ("Who approves what", "Account executives can give up to 10% discount on the first year. 10% to 20% needs the sales manager. Anything above 20%, or any multi-year price lock, needs the CFO."),
            ("Paperwork", "Log the approval in the deal record before sending the order form. Unlogged discounts are reversed at invoicing."),
        ],
    },
    {
        "id": "D-11", "title": "Customer data handling", "source": "notion", "path": "Company handbook / Security",
        "owner": "maya", "groups": ["all_staff", "contractors"], "discoverable": True, "updated": "2026-04-22", "review_by": "2027-04-22",
        "sections": [
            ("Rules", "Never copy customer data into personal tools, personal email or AI tools that are not on the approved list. Exports must be deleted within 30 days or when the ticket closes, whichever is first."),
            ("Requests from customers", "Forward any deletion or access request to the privacy inbox the same day. We have 30 days to answer under GDPR."),
        ],
    },
    {
        "id": "D-12", "title": "Laptops and home office", "source": "notion", "path": "Company handbook / Equipment",
        "owner": "ruth", "groups": ["all_staff", "contractors"], "discoverable": True, "updated": "2026-01-30", "review_by": "2027-01-30",
        "sections": [
            ("Laptops", "Employees and contractors get a company laptop, replaced every three years. Lost or stolen laptops must be reported to IT within 24 hours."),
            ("Home office budget", "Employees get a one-off EUR 400 home office budget in their first year and EUR 150 per year after that. Contractors are not eligible."),
        ],
    },
    {
        "id": "D-13", "title": "Reporting a security incident", "source": "notion", "path": "Company handbook / Security",
        "owner": "maya", "groups": ["all_staff", "contractors"], "discoverable": True, "updated": "2026-08-09", "review_by": "2027-08-09",
        "sections": [
            ("What to do", "If you click a suspicious link, lose a device or see data where it should not be, post in the security channel or page security within 1 hour. Do not try to investigate it yourself."),
        ],
    },
    {
        "id": "D-14", "title": "Benefits overview", "source": "confluence", "path": "HR / Benefits",
        "owner": "ruth", "groups": ["all_staff"], "discoverable": True, "updated": "2025-04-10", "review_by": "2026-04-10",
        "sections": [
            ("Health and wellbeing", "Private health insurance covers you and your dependants from your first day. The wellbeing allowance is EUR 40 per month for gym, sport or therapy."),
            ("Learning", "Each employee has a EUR 1,200 yearly learning budget for courses, books and conferences, approved by their manager."),
        ],
    },
    {
        "id": "D-15", "title": "Board pack Q3 2026", "source": "drive", "path": "Leadership / Board",
        "owner": "leo", "groups": ["leadership"], "discoverable": False, "updated": "2026-10-20", "review_by": "2027-01-20",
        "canary": "EUR 4.2 million",
        "sections": [
            ("Results", "Q3 revenue was EUR 4.2 million, 6% under plan, with net revenue retention of 108%. Runway is 22 months."),
        ],
    },
    {
        "id": "D-16", "title": "Contractor guide", "source": "confluence", "path": "HR / Contractors",
        "owner": "ruth", "groups": ["contractors", "people_ops"], "discoverable": True, "updated": "2026-05-05", "review_by": "2027-05-05",
        "sections": [
            ("Invoicing", "Contractors invoice monthly by the 5th working day, with hours by project. Invoices are paid within 14 days."),
            ("Time off", "Contractors are not on the employee leave scheme; tell your project lead about planned absences two weeks ahead."),
        ],
    },
    {
        "id": "D-17", "title": "Engineering career ladder", "source": "confluence", "path": "ENG / People",
        "owner": "maya", "groups": ["all_staff"], "discoverable": True, "updated": "2026-02-15", "review_by": "2027-02-15",
        "sections": [
            ("Levels", "Engineering has five levels, L1 to L5. Promotions are decided twice a year, in March and September, by a panel of two leads who did not manage you."),
        ],
    },
    {
        "id": "D-18", "title": "Payroll calendar", "source": "drive", "path": "Finance / Payroll",
        "owner": "ana", "groups": ["all_staff"], "discoverable": True, "updated": "2026-01-05", "review_by": "2027-01-05",
        "sections": [
            ("Pay day", "Salaries are paid on the 25th of each month, or the last working day before it. In December pay day is 20 December."),
            ("Payslips", "Payslips appear in the HR portal two working days before pay day."),
        ],
    },
]

DOC_BY_ID = {d["id"]: d for d in DOCS}


def chunks(docs=None):
    """Each section is one chunk; the title is part of what gets searched."""
    out = []
    for d in (DOCS if docs is None else docs):
        for i, (heading, text) in enumerate(d["sections"], start=1):
            out.append({
                "id": f"{d['id']}#{i}", "doc": d["id"], "heading": heading, "text": text,
                "search": f"{d['title']} {heading} {text}",
            })
    return out
