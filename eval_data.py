"""Evaluation dataset: multi-session conversations where facts change over time."""

SCENARIOS = [
    {
        "name": "billing",
        "sessions": [
            ("2026-10-01", "Priya is the owner of the billing migration. The deadline is Oct 20. We decided to use Stripe for payments."),
            ("2026-10-08", "Quick update: the billing migration deadline moved to Nov 3, and Rahul is taking over the migration from Priya."),
            ("2026-10-15", "We are switching from Stripe to Razorpay because of lower fees. The billing migration deadline is now Nov 10."),
        ],
        "questions": [
            {"q": "Who owns the billing migration?", "any_of": ["Rahul"], "none_of": ["Priya"]},
            {"q": "When is the billing migration deadline?", "any_of": ["Nov 10", "November 10"], "none_of": ["Oct 20", "October 20", "Nov 3", "November 3"]},
            {"q": "Which payment provider are we using?", "any_of": ["Razorpay"], "none_of": ["Stripe"]},
        ],
    },
    {
        "name": "meera",
        "sessions": [
            ("2026-10-02", "Meera prefers meetings in the morning. She uses Slack for team communication. Her team lead is Arjun."),
            ("2026-10-09", "Meera now prefers afternoon meetings, after 2 PM. Her new team lead is Sana."),
            ("2026-10-16", "Meera moved from Slack to Microsoft Teams for team communication."),
        ],
        "questions": [
            {"q": "When does Meera prefer to have meetings?", "any_of": ["afternoon", "2 PM"], "none_of": ["morning"]},
            {"q": "Who is Meera's team lead?", "any_of": ["Sana"], "none_of": ["Arjun"]},
            {"q": "Which tool does Meera use for team communication?", "any_of": ["Teams"], "none_of": ["Slack"]},
        ],
    },
    {
        "name": "mobile_app",
        "sessions": [
            ("2026-10-03", "The mobile app launch is planned for Dec 1. The backend is written in Node.js. The lead designer is Kavya. The project is currently in development."),
            ("2026-10-12", "The mobile app launch has been delayed to Jan 15. The project is now in QA testing."),
            ("2026-10-20", "The backend was rewritten in Go. Kavya left the team, and Tara is now the lead designer."),
        ],
        "questions": [
            {"q": "When is the mobile app launch?", "any_of": ["Jan 15"], "none_of": ["Dec 1"]},
            {"q": "What is the current status of the mobile app project?", "any_of": ["QA"], "none_of": ["in development"]},
            {"q": "What language is the backend written in?", "any_of": ["Go"], "none_of": ["Node"]},
            {"q": "Who is the lead designer?", "any_of": ["Tara"], "none_of": ["Kavya"]},
        ],
    },
    {
        "name": "ishan",
        "sessions": [
            ("2026-10-04", "Ishan is based in Pune. His manager is Neha. The weekly team sync is on Tuesday."),
            ("2026-10-18", "Ishan got a new laptop, a MacBook Pro. The weekly team sync moved to Thursday."),
        ],
        "questions": [
            {"q": "Which city is Ishan based in?", "any_of": ["Pune"], "none_of": []},
            {"q": "Who is Ishan's manager?", "any_of": ["Neha"], "none_of": []},
            {"q": "Which day is the weekly team sync?", "any_of": ["Thursday"], "none_of": ["Tuesday"]},
            {"q": "What laptop does Ishan have?", "any_of": ["MacBook"], "none_of": []},
        ],
    },
            {
        "name": "analytics_team",
        "sessions": [
            ("2026-10-05", "The analytics team uses PostgreSQL for reporting. Dana is the team lead. The standup is at 10 AM."),
            ("2026-10-13", "The analytics team is moving from PostgreSQL to ClickHouse because queries were too slow. The analytics team standup is now at 9:30 AM."),
            ("2026-10-21", "Dana was promoted, so Omar is taking over as the analytics team lead."),
        ],
        "questions": [
            {"q": "Which database does the analytics team use for reporting?", "any_of": ["ClickHouse"], "none_of": ["PostgreSQL", "Postgres"]},
            {"q": "Who is the analytics team lead?", "any_of": ["Omar"], "none_of": ["Dana"]},
            {"q": "What time is the analytics team standup?", "any_of": ["9:30"], "none_of": ["10 AM"]},
        ],
    },
        {
        "name": "kiran",
        "sessions": [
            ("2026-10-06", "Kiran works from the Bangalore office. Kiran's laptop is a Dell XPS. Kiran reports to Leela."),
            ("2026-10-14", "Kiran has relocated and now works from the Hyderabad office."),
            ("2026-10-22", "Kiran switched from the Dell XPS to a MacBook Air. Kiran now reports to Mohan."),
        ],
        "questions": [
            {"q": "Which office does Kiran work from?", "any_of": ["Hyderabad"], "none_of": ["Bangalore"]},
            {"q": "What laptop does Kiran use?", "any_of": ["MacBook"], "none_of": ["Dell"]},
            {"q": "Who does Kiran report to?", "any_of": ["Mohan"], "none_of": ["Leela"]},
        ],
    },
]
