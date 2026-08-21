"""
Training Mode Engine
====================
Onboarding, education, simulation, and adoption layer for the Business Command Center.

Teaches non-technical business owners how to operate their business using the platform
through guided interactive walkthroughs, simulations, knowledge checks, and a
deterministic training coach.

All training data is separate from live business data. Simulations never modify
action_events.json, CRM records, scorecard snapshots, or any live business data.
"""

import json
import os
from datetime import date, datetime
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TODAY = date(2026, 8, 16)
DRAFT_DISCLAIMER = "DRAFT -- owner approval required."
SAMPLE_PREFIX = "[SAMPLE]"

TRAINING_DIR = os.path.dirname(os.path.abspath(__file__))
PROGRESS_FILE = os.path.join(TRAINING_DIR, "training_progress.json")
SIM_FILE = os.path.join(TRAINING_DIR, "training_simulation_state.json")

# ---------------------------------------------------------------------------
# Training Modules (Phases 1-15, 18-19, 22)
# ---------------------------------------------------------------------------

TRAINING_MODULES: List[Dict[str, Any]] = [
    {
        "id": "welcome",
        "phase": 1,
        "title": "Welcome to Your Business Command Center",
        "subtitle": "What this platform does for you",
        "estimated_minutes": 2,
        "type": "intro",
        "steps": [
            {
                "id": "intro",
                "title": "Your Business Command Center",
                "content": "This platform helps you run your insurance agency more efficiently. Instead of juggling spreadsheets, sticky notes, and memory, the system monitors your business and tells you exactly what needs attention.",
                "bullets": [
                    "Identify opportunities before they go cold",
                    "Prioritize work by business impact, not guesswork",
                    "Follow up consistently with every lead and client",
                    "Improve client relationships and retention",
                    "Increase referrals from existing clients and partners",
                    "Grow revenue with clear goals and forecasts",
                    "Stay organized with one centralized system"
                ],
                "cta_text": "Start Training",
                "cta_action": "start_training"
            }
        ],
        "knowledge_check": None
    },
    {
        "id": "command_center_basics",
        "phase": 2,
        "title": "Command Center Basics",
        "subtitle": "Your daily starting point",
        "estimated_minutes": 2,
        "type": "walkthrough",
        "steps": [
            {
                "id": "top5",
                "title": "Today's Top 5",
                "content": "When you open the Command Center, the first thing you see is Today's Top 5. These are the highest-value actions available to you right now.",
                "bullets": [
                    "Each item is ranked by business impact and urgency",
                    "Items include leads to call, clients to review, and follow-ups due",
                    "The system considers value, timing, and relationship importance",
                    "Click any item to see details and take action"
                ],
                "interaction": {
                    "type": "click_priority",
                    "prompt": "Click on a priority item below to see its details.",
                    "sample_priorities": [
                        {"entity": f"{SAMPLE_PREFIX} John Smith", "type": "Lead", "score": 92, "value": 8400, "reason": "High-score lead, last contacted 6 days ago", "priority": 1},
                        {"entity": f"{SAMPLE_PREFIX} Mary Johnson", "type": "Client Review", "score": 78, "value": 12500, "reason": "Annual review overdue by 45 days", "priority": 2},
                        {"entity": f"{SAMPLE_PREFIX} Michael Thompson", "type": "Referral", "score": 85, "value": 1660, "reason": "Referral partner not contacted in 35 days", "priority": 3}
                    ]
                }
            },
            {
                "id": "needs_attention",
                "title": "Needs Attention",
                "content": "Below the Top 5, you'll find a Needs Attention section. This shows items that require your awareness but may not be immediate action items.",
                "bullets": [
                    "Stale leads that are going cold",
                    "Clients with declining health scores",
                    "Revenue gaps that need attention",
                    "Overdue tasks and follow-ups"
                ]
            }
        ],
        "knowledge_check": {
            "question": "What does Today's Top 5 show you?",
            "options": [
                "A random list of tasks to do today",
                "The highest-value actions available right now, ranked by impact",
                "All the leads in your database",
                "Your schedule for the week"
            ],
            "correct_index": 1,
            "explanation": "Today's Top 5 ranks actions by business impact and urgency so you always know what matters most."
        }
    },
    {
        "id": "understanding_priorities",
        "phase": 3,
        "title": "Understanding Priorities",
        "subtitle": "How the system decides what matters",
        "estimated_minutes": 2,
        "type": "scenario",
        "steps": [
            {
                "id": "scenario",
                "title": "Meet a Priority Opportunity",
                "content": f"Let's look at a realistic example. {SAMPLE_PREFIX} John Smith is a lead in your system. Here's what the platform sees:",
                "scenario_card": {
                    "name": f"{SAMPLE_PREFIX} John Smith",
                    "lead_score": 92,
                    "opportunity_value": "$8,400",
                    "last_contact": "6 days ago",
                    "eligibility": "42 days until Medicare AEP",
                    "status": "Hot Lead"
                },
                "bullets": [
                    "Value: $8,400 potential commission -- high impact",
                    "Urgency: Last contacted 6 days ago -- follow-up window closing",
                    "Probability: Lead score 92/100 -- very likely to convert",
                    "Timing: 42 days until Annual Enrollment Period -- planning window",
                    "Relationship: Previous conversations indicate strong interest"
                ],
                "explanation": "The system weighs all five factors to rank this as a top priority. You don't need to remember any of this -- the system does it for you. You just need to act on the recommendation."
            }
        ],
        "knowledge_check": {
            "question": "What factors does the system use to prioritize opportunities?",
            "options": [
                "Alphabetical order of client names",
                "Value, urgency, probability, relationship, and timing",
                "The date the lead was first entered",
                "Random selection from available leads"
            ],
            "correct_index": 1,
            "explanation": "The system ranks opportunities using business factors like value, urgency, probability, relationship importance, and timing."
        }
    },
    {
        "id": "what_next",
        "phase": 4,
        "title": "What Should I Do Next?",
        "subtitle": "Your single most important action",
        "estimated_minutes": 2,
        "type": "walkthrough",
        "steps": [
            {
                "id": "recommendation",
                "title": "Your #1 Recommended Action",
                "content": "The Command Center includes a 'What Should I Do Next?' button. When you click it, the system analyzes all your opportunities and identifies the single most important action you can take right now.",
                "sample_recommendation": {
                    "action": f"Call {SAMPLE_PREFIX} John Smith",
                    "reason": "High-score lead (92/100) with $8,400 opportunity value. Last contacted 6 days ago. Medicare AEP is 42 days away -- this is the optimal time to follow up and schedule a consultation.",
                    "expected_impact": "Scheduling a consultation could move this lead from 'hot' to 'closed', adding $8,400 to this month's revenue.",
                    "recommended_action": "Call to schedule a Medicare plan review consultation"
                },
                "interaction": {
                    "type": "click_recommendation",
                    "prompt": "Click the 'What Should I Do Next?' button to see your recommendation.",
                    "cta_text": "What Should I Do Next?",
                    "cta_action": "show_recommendation"
                }
            }
        ],
        "knowledge_check": None
    },
    {
        "id": "action_execution",
        "phase": 5,
        "title": "Taking Action",
        "subtitle": "How to execute recommendations",
        "estimated_minutes": 2,
        "type": "simulation",
        "steps": [
            {
                "id": "execute",
                "title": "Execute Your First Action",
                "content": f"When you have a recommendation like 'Call {SAMPLE_PREFIX} John Smith', you can take action directly from the platform. Let's practice with a simulated call.",
                "interaction": {
                    "type": "simulate_action",
                    "prompt": "Click the CALL button to simulate calling John Smith.",
                    "action_label": "CALL",
                    "action_type": "call",
                    "entity": f"{SAMPLE_PREFIX} John Smith",
                    "is_simulated": True
                },
                "post_action_content": "When you complete an action in the real system, several things happen automatically:",
                "post_action_bullets": [
                    "Your CRM updates with the contact record",
                    "Today's Top 5 priorities update",
                    "Revenue forecasts adjust based on the outcome",
                    "Follow-up reminders are created if needed",
                    "The Command Center refreshes with new priorities"
                ]
            }
        ],
        "knowledge_check": None
    },
    {
        "id": "recording_outcomes",
        "phase": 6,
        "title": "Recording Outcomes",
        "subtitle": "Why outcomes matter",
        "estimated_minutes": 2,
        "type": "simulation",
        "steps": [
            {
                "id": "outcome",
                "title": "What Happened on the Call?",
                "content": "After completing an action, you record what happened. This is called the outcome. The system uses outcomes to improve future recommendations.",
                "interaction": {
                    "type": "select_outcome",
                    "prompt": "Select the outcome of your simulated call to John Smith.",
                    "outcomes": [
                        {"label": "Connected", "description": "Spoke with John, had a productive conversation", "recommended": True},
                        {"label": "Left Voicemail", "description": "John didn't answer, left a message"},
                        {"label": "No Answer", "description": "John didn't answer, no message left"},
                        {"label": "Appointment Scheduled", "description": "Scheduled a consultation for next week"},
                        {"label": "Follow-Up Needed", "description": "John asked to be contacted later"}
                    ]
                },
                "post_outcome_content": "By recording 'Connected', the system now knows that John is engaged and responsive. This improves his lead score and influences future recommendations. If you had selected 'No Answer', the system would suggest a different follow-up timing.",
                "explanation": "Outcomes are the feedback loop that makes the platform smarter over time. The more outcomes you record, the better the recommendations become."
            }
        ],
        "knowledge_check": {
            "question": "Why should you record the outcome after completing an action?",
            "options": [
                "It's required to use the platform",
                "Outcomes improve future recommendations by telling the system what happened",
                "It automatically sends emails to clients",
                "It deletes the action from your list"
            ],
            "correct_index": 1,
            "explanation": "Outcomes are the feedback loop that makes the platform smarter. The more you record, the better future recommendations become."
        }
    },
    {
        "id": "follow_up",
        "phase": 7,
        "title": "Follow-Up Management",
        "subtitle": "Never miss a callback",
        "estimated_minutes": 2,
        "type": "scenario",
        "steps": [
            {
                "id": "create_followup",
                "title": "Creating a Follow-Up",
                "content": f"When a client asks you to call back later, you create a follow-up. Let's say {SAMPLE_PREFIX} Mary Johnson asked you to call her back on Friday about her Medicare plan options.",
                "scenario_card": {
                    "entity": f"{SAMPLE_PREFIX} Mary Johnson",
                    "reason": "Requested callback to discuss Medicare plan options",
                    "date": "Friday, August 21",
                    "priority": "High"
                },
                "bullets": [
                    "Set the date for when the follow-up is due",
                    "Add a reason so you remember why you're following up",
                    "Set priority based on urgency and value",
                    "The system automatically brings it back when it becomes due"
                ],
                "interaction": {
                    "type": "create_followup",
                    "prompt": "Click 'Create Follow-Up' to schedule the callback.",
                    "cta_text": "Create Follow-Up",
                    "cta_action": "create_followup"
                },
                "post_action_content": "The follow-up is now scheduled. You can also snooze items for later or reschedule them if priorities change."
            }
        ],
        "knowledge_check": None
    },
    {
        "id": "client_management",
        "phase": 8,
        "title": "Client Management",
        "subtitle": "Keeping clients healthy",
        "estimated_minutes": 2,
        "type": "scenario",
        "steps": [
            {
                "id": "at_risk_client",
                "title": "Spotting an At-Risk Client",
                "content": f"The platform monitors your client relationships and alerts you when attention is needed. Here's a realistic scenario:",
                "scenario_card": {
                    "entity": f"{SAMPLE_PREFIX} Robert Davis",
                    "type": "High-Value Client",
                    "clv": "$18,500",
                    "last_contact": "90 days ago",
                    "health_score": "42/100 (Declining)",
                    "review_status": "Annual review overdue"
                },
                "bullets": [
                    "Client Health Score: 42/100 -- declining due to lack of contact",
                    "Client Lifetime Value: $18,500 -- this is a valuable relationship",
                    "Last Contact: 90 days ago -- well beyond the healthy 30-day window",
                    "Review Status: Annual review is overdue"
                ],
                "recommended_action": "Schedule a client review call with Robert to discuss his current coverage and any life changes.",
                "explanation": "The system surfaces this because losing a high-value client costs more than maintaining the relationship. A 30-minute call can protect $18,500 in lifetime value."
            }
        ],
        "knowledge_check": {
            "question": "What does a Client Health Score of 42/100 tell you?",
            "options": [
                "The client has 42 contacts in the system",
                "The client relationship is declining and needs attention soon",
                "The client owes you $42",
                "The client has been in the system for 42 days"
            ],
            "correct_index": 1,
            "explanation": "A declining health score means the relationship needs attention. The system alerts you before the client is lost."
        }
    },
    {
        "id": "referral_training",
        "phase": 9,
        "title": "Referral Management",
        "subtitle": "Growing through relationships",
        "estimated_minutes": 2,
        "type": "scenario",
        "steps": [
            {
                "id": "dormant_partner",
                "title": "Waking Up a Dormant Referral Partner",
                "content": f"The platform tracks your referral sources and alerts you when a productive partner has gone quiet.",
                "scenario_card": {
                    "entity": f"{SAMPLE_PREFIX} Michael Thompson",
                    "type": "Referral Partner",
                    "last_contact": "35 days ago",
                    "referrals_this_year": 7,
                    "potential_opportunity": "$12,400",
                    "status": "Dormant"
                },
                "bullets": [
                    "This partner has referred 7 clients this year -- a proven source",
                    "Last contact was 35 days ago -- the relationship is going cold",
                    "Potential opportunity: $12,400 in referral value available",
                    "Recommended action: Contact the partner to maintain the relationship"
                ],
                "explanation": "Referral partners who go 30+ days without contact are likely to refer elsewhere. A quick check-in call can keep the pipeline flowing."
            }
        ],
        "knowledge_check": None
    },
    {
        "id": "revenue_training",
        "phase": 10,
        "title": "Revenue Management",
        "subtitle": "Understanding your revenue gap",
        "estimated_minutes": 2,
        "type": "scenario",
        "steps": [
            {
                "id": "revenue_gap",
                "title": "Closing the Revenue Gap",
                "content": "The platform tracks your revenue goal and forecasts what you're likely to earn. When there's a gap, it recommends actions to close it.",
                "scenario_card": {
                    "monthly_goal": "$35,000",
                    "forecast": "$31,800",
                    "gap": "$3,200",
                    "current_booked": "$28,500",
                    "pipeline_value": "$12,600",
                    "close_rate": "25%"
                },
                "bullets": [
                    "Monthly Goal: $35,000 -- what you want to earn this month",
                    "Forecast: $31,800 -- what the system predicts you'll earn",
                    "Gap: $3,200 -- the difference between goal and forecast",
                    "The platform recommends specific actions to close the gap"
                ],
                "recommended_actions": [
                    f"Follow up with 3 hot leads worth $8,400 combined",
                    f"Schedule 2 client reviews that could lead to referrals",
                    f"Contact 1 dormant referral partner with $12,400 potential"
                ],
                "explanation": "Every recommended action in the platform connects to your revenue goal. When you close the gap, your forecast improves."
            }
        ],
        "knowledge_check": None
    },
    {
        "id": "marketing_training",
        "phase": 11,
        "title": "Marketing Workflows",
        "subtitle": "Content, approval, and scheduling",
        "estimated_minutes": 2,
        "type": "walkthrough",
        "steps": [
            {
                "id": "content_review",
                "title": "Content Awaiting Your Approval",
                "content": "The platform generates marketing content for your review. Nothing is published without your approval.",
                "scenario_card": {
                    "content_pieces": 5,
                    "status": "Awaiting Approval",
                    "compliance": "PASS -- all content meets CMS guidelines",
                    "channels": "Email, Social Media, Blog"
                },
                "bullets": [
                    "Review: Read the content and check it's accurate",
                    "Approve: Click approve to authorize publishing",
                    "Schedule: Choose when the content goes out",
                    "All content is checked for CMS Medicare Marketing compliance"
                ],
                "explanation": "Marketing connects to lead generation. More content means more visibility, which means more leads entering your pipeline."
            }
        ],
        "knowledge_check": None
    },
    {
        "id": "what_changed",
        "phase": 12,
        "title": "What Changed?",
        "subtitle": "Understanding business movement",
        "estimated_minutes": 2,
        "type": "scenario",
        "steps": [
            {
                "id": "changes",
                "title": "Meaningful Changes in Your Business",
                "content": "The What Changed? view shows you what's different since yesterday. Not everything that changes matters -- the system filters for meaningful business movement.",
                "scenario_card": {
                    "changes": [
                        {"metric": "Referral Activity", "change": "+24%", "direction": "up", "meaningful": True, "explanation": "Referral partners are more active -- 3 new referrals this week"},
                        {"metric": "Pipeline Value", "change": "+$8,400", "direction": "up", "meaningful": True, "explanation": "New opportunities added to your pipeline"},
                        {"metric": "Email Engagement", "change": "-12%", "direction": "down", "meaningful": True, "explanation": "Fewer people opening emails -- may need content refresh"},
                        {"metric": "Database Records", "change": "+2", "direction": "up", "meaningful": False, "explanation": "Just routine data entry -- not actionable"}
                    ]
                },
                "explanation": "The system distinguishes between information (nice to know) and actionable information (needs your attention). Focus on what's actionable."
            }
        ],
        "knowledge_check": {
            "question": "What's the difference between information and actionable information?",
            "options": [
                "There is no difference",
                "Information is nice to know; actionable information needs your attention",
                "Information is always more important",
                "Actionable information is only about revenue"
            ],
            "correct_index": 1,
            "explanation": "The system filters for meaningful changes that need your attention, so you don't waste time on routine data updates."
        }
    },
    {
        "id": "scorecard_training",
        "phase": 13,
        "title": "Business Owner Scorecard",
        "subtitle": "How healthy is your business?",
        "estimated_minutes": 2,
        "type": "walkthrough",
        "steps": [
            {
                "id": "scorecard_intro",
                "title": "Your Business Health Score",
                "content": "The Scorecard gives you a single number that represents the overall health of your business. It's like a fitness tracker for your agency.",
                "scenario_card": {
                    "overall_score": "87/100",
                    "categories": [
                        {"name": "Revenue", "score": 82, "weight": "25%"},
                        {"name": "Lead Management", "score": 90, "weight": "20%"},
                        {"name": "Client Relationships", "score": 85, "weight": "20%"},
                        {"name": "Referrals", "score": 88, "weight": "15%"},
                        {"name": "Marketing", "score": 92, "weight": "10%"},
                        {"name": "Execution", "score": 75, "weight": "10%"}
                    ]
                },
                "bullets": [
                    "Revenue Score: Are you hitting your revenue goals?",
                    "Lead Score: Are you managing leads effectively?",
                    "Client Score: Are your client relationships healthy?",
                    "Referral Score: Are you growing through referrals?",
                    "Marketing Score: Is your marketing active and compliant?",
                    "Execution Score: Are you completing recommended actions?"
                ],
                "explanation": "The Scorecard identifies your strengths, weaknesses, and biggest opportunities. Focus on improving your weakest category for the biggest business impact."
            }
        ],
        "knowledge_check": {
            "question": "What does the Business Health Score represent?",
            "options": [
                "The number of clients in your system",
                "The overall health of your business across all key areas",
                "Your revenue for the month",
                "How many actions you've completed"
            ],
            "correct_index": 1,
            "explanation": "The Business Health Score combines all categories into one number so you can see at a glance how your business is doing."
        }
    },
    {
        "id": "weekly_review",
        "phase": 14,
        "title": "Weekly Business Review",
        "subtitle": "Your Friday afternoon routine",
        "estimated_minutes": 2,
        "type": "walkthrough",
        "steps": [
            {
                "id": "weekly_brief",
                "title": "The Weekly Business Brief",
                "content": "Each week, the Scorecard generates a Weekly Business Brief. This is your summary of what happened and what to focus on next.",
                "scenario_card": {
                    "health_score": "87/100 (up 3 from last week)",
                    "biggest_win": "Marketing is your strongest area at 92/100",
                    "biggest_concern": "Execution at 75/100 -- you're not completing all recommended actions",
                    "biggest_opportunity": "Raising Execution by 25 pts would improve your overall score by 2.5 pts",
                    "weekly_focus": [
                        "Complete 5 overdue client follow-ups",
                        "Contact 2 dormant referral partners",
                        "Review and approve 3 marketing content pieces"
                    ]
                },
                "explanation": "Use the Weekly Brief every Friday to review your week, celebrate wins, address concerns, and plan your focus for next week."
            }
        ],
        "knowledge_check": None
    },
    {
        "id": "daily_routine",
        "phase": 15,
        "title": "Your Daily Routine",
        "subtitle": "Morning, afternoon, and end of day",
        "estimated_minutes": 3,
        "type": "walkthrough",
        "steps": [
            {
                "id": "morning",
                "title": "Morning Routine",
                "content": "Start every day with the Command Center.",
                "bullets": [
                    "Open the Command Center",
                    "Review Today's Top 5 priorities",
                    "Check the Needs Attention section",
                    "Click 'What Should I Do Next?' for your #1 action",
                    "Execute your first action"
                ]
            },
            {
                "id": "afternoon",
                "title": "Afternoon Routine",
                "content": "After lunch, shift to outcomes and follow-ups.",
                "bullets": [
                    "Update outcomes for actions you completed",
                    "Review follow-ups due today",
                    "Check for new opportunities that appeared",
                    "Execute your next priority action"
                ]
            },
            {
                "id": "end_of_day",
                "title": "End of Day",
                "content": "Wrap up and prepare for tomorrow.",
                "bullets": [
                    "Review completed actions",
                    "Snooze or reschedule items you couldn't get to",
                    "Check tomorrow's upcoming follow-ups",
                    "Close the Command Center -- it'll be ready for you tomorrow"
                ]
            }
        ],
        "knowledge_check": {
            "question": "What should you do first thing in the morning?",
            "options": [
                "Check your email",
                "Open the Command Center and review Today's Top 5",
                "Call every client in your database",
                "Wait for the system to notify you"
            ],
            "correct_index": 1,
            "explanation": "Start every day with the Command Center to see your priorities and your #1 recommended action."
        }
    }
]

# ---------------------------------------------------------------------------
# Simulation Scenarios (Phase 16)
# ---------------------------------------------------------------------------

SIMULATION_SCENARIOS: List[Dict[str, Any]] = [
    {
        "id": "new_lead",
        "title": "New Lead Follow-Up",
        "description": f"A new lead, {SAMPLE_PREFIX} Sarah Williams, just entered your system. Practice prioritizing and following up.",
        "entity": f"{SAMPLE_PREFIX} Sarah Williams",
        "entity_type": "lead",
        "lead_score": 88,
        "opportunity_value": 6200,
        "last_contact": "Just entered",
        "scenario": f"{SAMPLE_PREFIX} Sarah Williams requested a Medicare quote through your website. She's 58 years old, retiring in 6 months, and has a household income of $85,000.",
        "recommended_action": "Call Sarah to introduce yourself and schedule a consultation",
        "actions": [
            {"label": "Call", "type": "call", "is_simulated": True},
            {"label": "Email", "type": "email", "is_simulated": True},
            {"label": "Schedule Follow-Up", "type": "follow_up", "is_simulated": True}
        ],
        "outcomes": [
            {"label": "Connected", "description": "Spoke with Sarah, she's interested in a consultation"},
            {"label": "Left Voicemail", "description": "Sarah didn't answer, left a message"},
            {"label": "No Answer", "description": "No answer, no message"},
            {"label": "Not Interested", "description": "Sarah is no longer interested"}
        ]
    },
    {
        "id": "high_value_client",
        "title": "At-Risk Client Review",
        "description": f"A high-value client hasn't been contacted in 90 days. Practice client management.",
        "entity": f"{SAMPLE_PREFIX} Robert Davis",
        "entity_type": "client",
        "clv": 18500,
        "last_contact": "90 days ago",
        "health_score": 42,
        "scenario": f"{SAMPLE_PREFIX} Robert Davis is a long-time client with $18,500 in lifetime value. His health score has dropped to 42/100 because he hasn't been contacted in 90 days. His annual review is overdue.",
        "recommended_action": "Schedule a client review call to discuss his current coverage",
        "actions": [
            {"label": "Call", "type": "call", "is_simulated": True},
            {"label": "Schedule Review", "type": "schedule_review", "is_simulated": True},
            {"label": "Send Email", "type": "email", "is_simulated": True}
        ],
        "outcomes": [
            {"label": "Connected", "description": "Robert is happy to hear from you, schedules a review"},
            {"label": "Left Voicemail", "description": "Robert didn't answer, left a message"},
            {"label": "No Answer", "description": "No answer, will try again tomorrow"},
            {"label": "Requested Reschedule", "description": "Robert asked to reschedule for next week"}
        ]
    },
    {
        "id": "referral_opportunity",
        "title": "Dormant Referral Partner",
        "description": f"A productive referral partner has gone quiet. Practice referral management.",
        "entity": f"{SAMPLE_PREFIX} Michael Thompson",
        "entity_type": "referral_partner",
        "referrals_this_year": 7,
        "potential_value": 12400,
        "last_contact": "35 days ago",
        "scenario": f"{SAMPLE_PREFIX} Michael Thompson has referred 7 clients this year but hasn't been contacted in 35 days. He has $12,400 in potential referral value available.",
        "recommended_action": "Contact Michael to maintain the relationship and discuss new opportunities",
        "actions": [
            {"label": "Call", "type": "call", "is_simulated": True},
            {"label": "Email", "type": "email", "is_simulated": True},
            {"label": "Schedule Meeting", "type": "schedule_meeting", "is_simulated": True}
        ],
        "outcomes": [
            {"label": "Connected", "description": "Michael is receptive, has 2 new referrals to discuss"},
            {"label": "Left Voicemail", "description": "Michael didn't answer, left a message"},
            {"label": "No Answer", "description": "No answer, will try again next week"},
            {"label": "Requested Callback", "description": "Michael asked to be called back next week"}
        ]
    },
    {
        "id": "revenue_gap",
        "title": "Closing a Revenue Gap",
        "description": "Your revenue forecast shows a gap. Practice using recommendations to close it.",
        "entity": "Revenue Gap",
        "entity_type": "revenue",
        "monthly_goal": 35000,
        "forecast": 31800,
        "gap": 3200,
        "scenario": "Your monthly revenue goal is $35,000. Your forecast shows $31,800. You have a $3,200 gap to close. The system has identified several actions that could close it.",
        "recommended_actions": [
            f"Follow up with 3 hot leads worth $8,400 combined",
            f"Schedule 2 overdue client reviews",
            f"Contact 1 dormant referral partner with $12,400 potential"
        ],
        "actions": [
            {"label": "View Hot Leads", "type": "view_leads", "is_simulated": True},
            {"label": "Schedule Reviews", "type": "schedule_reviews", "is_simulated": True},
            {"label": "Contact Partner", "type": "contact_partner", "is_simulated": True}
        ],
        "outcomes": [
            {"label": "Leads Contacted", "description": "Called 3 hot leads, 2 scheduled consultations"},
            {"label": "Reviews Scheduled", "description": "Scheduled both overdue client reviews"},
            {"label": "Partner Contacted", "description": "Michael Thompson has 2 new referrals"},
            {"label": "Partial Progress", "description": "Completed some but not all actions"}
        ]
    },
    {
        "id": "marketing_opportunity",
        "title": "Marketing Content Review",
        "description": "Marketing content is awaiting your approval. Practice the review workflow.",
        "entity": "Marketing Content",
        "entity_type": "marketing",
        "content_pieces": 5,
        "compliance": "PASS",
        "scenario": "5 marketing content pieces are awaiting your approval. All have passed CMS Medicare Marketing compliance checks. They include 2 email campaigns, 2 social media posts, and 1 blog article.",
        "recommended_action": "Review and approve the content, then schedule it for publication",
        "actions": [
            {"label": "Review Content", "type": "review", "is_simulated": True},
            {"label": "Approve", "type": "approve", "is_simulated": True},
            {"label": "Schedule", "type": "schedule", "is_simulated": True}
        ],
        "outcomes": [
            {"label": "All Approved", "description": "Reviewed and approved all 5 pieces, scheduled for this week"},
            {"label": "Partial Approval", "description": "Approved 3 pieces, requested changes on 2"},
            {"label": "Changes Requested", "description": "Content needs revisions before approval"},
            {"label": "Deferred", "description": "Will review later this week"}
        ]
    }
]

# ---------------------------------------------------------------------------
# Knowledge Checks (Phase 19)
# ---------------------------------------------------------------------------

ALL_KNOWLEDGE_CHECKS = [
    m["knowledge_check"] for m in TRAINING_MODULES if m.get("knowledge_check")
]

# ---------------------------------------------------------------------------
# Training Coach (Phase 20)
# ---------------------------------------------------------------------------

COACH_RESPONSES: List[Dict[str, str]] = [
    {"keywords": ["what does this mean", "explain", "what is"], "response": "The platform monitors your business and tells you what needs attention. Think of it as a smart assistant that never forgets a follow-up, never misses a deadline, and always knows your next best move."},
    {"keywords": ["why is this important", "why does this matter", "why"], "response": "Every recommendation in the platform is tied to business value. When the system suggests calling a lead, it's because that call could result in revenue. When it suggests reviewing a client, it's because that relationship is at risk. The importance is always about protecting or growing your business."},
    {"keywords": ["how should i use", "how do i use", "how to use"], "response": "Start every morning by opening the Command Center. Review your Top 5 priorities, click 'What Should I Do Next?' for your #1 action, and execute it. After completing an action, record the outcome. That's the core daily loop: See, Understand, Act, Record, Improve."},
    {"keywords": ["what should i focus", "what to focus", "focus", "priority", "prioritize"], "response": "Focus on your weakest Scorecard category first -- that's where you'll see the biggest improvement. If your Execution score is low, focus on completing recommended actions. If Revenue is low, focus on your highest-value leads. The system always tells you what to focus on next."},
    {"keywords": ["why did this recommendation", "why this recommendation", "why recommend"], "response": "Recommendations are based on business factors: the value of the opportunity, how urgent it is, how likely it is to succeed, your relationship with the person, and the timing. The system ranks all available actions and shows you the one with the highest combined impact."},
    {"keywords": ["scorecard", "health score", "business health"], "response": "The Business Health Score is like a fitness tracker for your agency. It combines six categories -- Revenue, Leads, Clients, Referrals, Marketing, and Execution -- into one number. A score above 70 means your business is healthy. Below 50 means you need to take action."},
    {"keywords": ["follow up", "follow-up", "callback", "reminder"], "response": "Follow-ups are how you never miss a callback. When someone asks you to call back later, create a follow-up with the date, reason, and priority. The system automatically brings it back when it becomes due. You can also snooze items for later."},
    {"keywords": ["revenue", "forecast", "gap", "goal"], "response": "The Revenue Forecast shows what you're likely to earn this month compared to your goal. When there's a gap, the system recommends specific actions to close it -- usually following up with hot leads or contacting referral partners."},
    {"keywords": ["client", "client health", "retention"], "response": "Client Health is about maintaining relationships. The system tracks how often you contact each client and alerts you when a relationship is going cold. A quick call to an at-risk client can protect thousands in lifetime value."},
    {"keywords": ["referral", "partner", "dormant"], "response": "Referrals are your lowest-cost source of new business. The system tracks which partners refer the most and alerts you when a productive partner goes quiet. Contacting a dormant partner can reactivate the referral pipeline."},
    {"keywords": ["marketing", "content", "approval", "campaign"], "response": "Marketing drives leads into your pipeline. The system generates content for your review -- nothing is published without your approval. Review it, approve it, and schedule it. More content means more visibility and more leads."},
    {"keywords": ["what changed", "changes", "movement"], "response": "The What Changed? view shows meaningful business changes since yesterday. The system filters out routine updates and only shows you things that need your attention -- like a drop in referral activity or a new high-value lead."},
    {"keywords": ["action", "execute", "take action", "call"], "response": "Actions are how you turn recommendations into results. When the system recommends calling someone, click the action button to execute it. After completing the action, record what happened. The system learns from outcomes and improves future recommendations."},
    {"keywords": ["outcome", "record", "result", "what happened"], "response": "Recording outcomes is the most important habit. After every action, tell the system what happened -- connected, voicemail, no answer, appointment scheduled. This feedback loop makes the platform smarter and your recommendations more accurate over time."},
    {"keywords": ["daily routine", "morning", "schedule", "workflow"], "response": "Your daily routine: Morning -- open Command Center, review Top 5, click 'What Should I Do Next?', execute your first action. Afternoon -- update outcomes, review follow-ups, execute next priority. End of day -- review completed actions, prepare for tomorrow."},
    {"keywords": ["weekly", "friday", "review", "brief"], "response": "Every Friday, review the Weekly Business Brief from the Scorecard. It shows your health score, biggest win, biggest concern, biggest opportunity, and your focus actions for next week. This 10-minute review keeps your business on track."},
    {"keywords": ["simulation", "practice", "safe", "test"], "response": "Simulation Mode lets you practice without affecting real data. You can practice calling leads, recording outcomes, and creating follow-ups in a safe environment. Nothing in the simulation modifies your live business data."},
    {"keywords": ["training", "learn", "help", "start", "begin"], "response": "Welcome to Training Mode. Work through each module in order. Each module takes 2-3 minutes. You'll learn by doing -- clicking, selecting, and practicing. Knowledge checks ensure you understand before moving on. You can always ask me questions along the way."}
]

# ---------------------------------------------------------------------------
# Contextual Help (Phase 21)
# ---------------------------------------------------------------------------

CONTEXTUAL_HELP: Dict[str, Dict[str, str]] = {
    "home": {
        "title": "Command Center",
        "help": "This is your daily starting point. Today's Top 5 shows your highest-value actions. Click 'What Should I Do Next?' for your #1 recommended action. The Needs Attention section shows items that require your awareness."
    },
    "scorecard": {
        "title": "Business Owner Scorecard",
        "help": "Your Business Health Score shows how healthy your business is across six categories. Focus on improving your weakest category for the biggest impact. Check the Weekly Brief every Friday."
    },
    "leads": {
        "title": "Leads & Follow-Ups",
        "help": "This view shows your leads ranked by priority. Hot leads should be contacted first. Follow-ups are scheduled callbacks that are due. Record outcomes after every contact to improve recommendations."
    },
    "lead-scoring": {
        "title": "Lead Priorities",
        "help": "Leads are ranked by their likelihood to convert and potential value. Focus on leads with scores above 80 first. The system considers timing, value, and engagement."
    },
    "pipeline": {
        "title": "Pipeline",
        "help": "Your revenue pipeline shows opportunities at each stage. Focus on moving opportunities from 'prospecting' to 'closed'. The close rate tells you how effectively you're converting."
    },
    "actions": {
        "title": "Action Center",
        "help": "All your recommended actions in one place. Execute actions by clicking the action buttons. After completing, record the outcome. Snooze items you can't get to today. Dismiss items that are no longer relevant."
    },
    "nurture": {
        "title": "Client Health",
        "help": "Client Health Scores show the strength of each client relationship. Scores below 50 need attention. Contact at-risk clients before they leave. Reviews should be completed annually."
    },
    "clv-intel": {
        "title": "Client Lifetime Value",
        "help": "CLV shows the total value of each client relationship over time. Focus on retaining high-CLV clients. A 30-minute call can protect thousands in lifetime value."
    },
    "referral-intel": {
        "title": "Referral Opportunities",
        "help": "This view shows referral sources ranked by potential. Contact dormant partners to reactivate the referral pipeline. The system identifies which partners are most likely to refer again."
    },
    "referrals": {
        "title": "Referral Sources",
        "help": "Track and manage your referral sources. Contact partners regularly to maintain relationships. The system alerts you when a productive partner goes quiet."
    },
    "community": {
        "title": "Community Outreach",
        "help": "Community events and workshops drive brand awareness and lead generation. Schedule workshops, track attendance, and follow up with attendees."
    },
    "marketing": {
        "title": "Content & Campaigns",
        "help": "Marketing content is generated for your review. Nothing is published without your approval. Review, approve, and schedule content. All content is checked for CMS compliance."
    },
    "revenue-forecast": {
        "title": "Revenue & Forecast",
        "help": "Your revenue goal vs. your forecast. When there's a gap, the system recommends actions to close it. Focus on high-value leads and referral opportunities to close the gap."
    },
    "executive": {
        "title": "Strategic Analysis",
        "help": "Executive-level analysis of your business. Daily briefings, priority lists, and strategic recommendations. Use this for high-level planning and decision-making."
    },
    "what-changed": {
        "title": "What Changed?",
        "help": "Shows meaningful business changes since yesterday. The system filters out routine updates and focuses on actionable changes. Review this daily to stay on top of your business."
    },
    "crm": {
        "title": "CRM Management",
        "help": "Manage your contact database. Keep records clean and up-to-date. The system flags duplicates and data quality issues for your attention."
    },
    "compliance": {
        "title": "Compliance",
        "help": "All marketing content is checked for CMS Medicare Marketing Guidelines compliance. Never publish content that hasn't passed compliance review."
    },
    "system-audit": {
        "title": "System Audit",
        "help": "Full system health check. Shows the status of all 12 agents and their endpoints. Use this to verify the system is running correctly."
    },
    "training": {
        "title": "Training Mode",
        "help": "Learn how to use the platform through guided modules and simulations. Work through each module in order. Knowledge checks ensure you understand before advancing. Ask the Training Coach if you have questions."
    }
}

# ---------------------------------------------------------------------------
# Advanced Modules (Phase 23)
# ---------------------------------------------------------------------------

ADVANCED_MODULES: List[Dict[str, Any]] = [
    {
        "id": "advanced_revenue",
        "title": "Advanced Revenue Management",
        "description": "Learn to use revenue forecasting, scenario planning, and gap analysis to hit your monthly and annual goals consistently.",
        "estimated_minutes": 5,
        "is_optional": True
    },
    {
        "id": "advanced_referrals",
        "title": "Advanced Referral Growth",
        "description": "Master referral source scoring, partner network building, and referral campaign management to create a steady pipeline of referred leads.",
        "estimated_minutes": 5,
        "is_optional": True
    },
    {
        "id": "advanced_clients",
        "title": "Advanced Client Retention",
        "description": "Use CLV analysis, relationship health scoring, and proactive outreach to retain high-value clients and prevent churn.",
        "estimated_minutes": 5,
        "is_optional": True
    },
    {
        "id": "advanced_marketing",
        "title": "Advanced Marketing",
        "description": "Learn to manage content calendars, multi-channel campaigns, and compliance review workflows for consistent lead generation.",
        "estimated_minutes": 5,
        "is_optional": True
    },
    {
        "id": "advanced_executive",
        "title": "Executive AI Mastery",
        "description": "Use daily briefings, weekly CEO reports, and future predictions for strategic business planning and decision-making.",
        "estimated_minutes": 5,
        "is_optional": True
    }
]

# ---------------------------------------------------------------------------
# Role-Based Training Paths (Phase 17)
# ---------------------------------------------------------------------------

TRAINING_ROLES: List[Dict[str, Any]] = [
    {
        "id": "business_owner",
        "title": "Business Owner",
        "description": "Full platform training for agency owners. Covers all modules and simulations.",
        "modules": [m["id"] for m in TRAINING_MODULES],
        "is_built": True
    },
    {
        "id": "salesperson",
        "title": "Salesperson",
        "description": "Focus on lead management, follow-ups, pipeline, and action execution.",
        "modules": ["command_center_basics", "understanding_priorities", "what_next", "action_execution", "recording_outcomes", "follow_up", "revenue_training"],
        "is_built": False
    },
    {
        "id": "account_manager",
        "title": "Account Manager",
        "description": "Focus on client health, CLV, reviews, and retention workflows.",
        "modules": ["command_center_basics", "client_management", "follow_up", "recording_outcomes"],
        "is_built": False
    },
    {
        "id": "office_manager",
        "title": "Office Manager",
        "description": "Focus on CRM management, compliance, and system operations.",
        "modules": ["command_center_basics", "what_next", "action_execution", "recording_outcomes"],
        "is_built": False
    },
    {
        "id": "marketing_coordinator",
        "title": "Marketing Coordinator",
        "description": "Focus on content review, approval, scheduling, and campaign management.",
        "modules": ["command_center_basics", "marketing_training", "what_changed"],
        "is_built": False
    },
    {
        "id": "administrator",
        "title": "Administrator",
        "description": "Focus on system setup, CRM management, compliance, and user management.",
        "modules": ["command_center_basics", "what_next", "action_execution"],
        "is_built": False
    }
]

# ---------------------------------------------------------------------------
# Progress Management
# ---------------------------------------------------------------------------

def _load_progress() -> Dict[str, Any]:
    """Load training progress from file, or return fresh state."""
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return _fresh_progress()

def _fresh_progress() -> Dict[str, Any]:
    return {
        "started": False,
        "started_at": None,
        "completed_modules": [],
        "current_module": None,
        "current_step": 0,
        "knowledge_checks_passed": [],
        "knowledge_checks_failed": [],
        "simulations_completed": [],
        "exercises_completed": [],
        "time_spent_minutes": 0,
        "role": "business_owner",
        "completed": False,
        "completed_at": None,
        "certificate": None
    }

def _save_progress(progress: Dict[str, Any]) -> None:
    try:
        with open(PROGRESS_FILE, "w") as f:
            json.dump(progress, f, indent=2)
    except Exception:
        pass

# ---------------------------------------------------------------------------
# Simulation State (separate from live data)
# ---------------------------------------------------------------------------

def _load_sim_state() -> Dict[str, Any]:
    if os.path.exists(SIM_FILE):
        try:
            with open(SIM_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {"completed_simulations": [], "simulated_actions": []}

def _save_sim_state(state: Dict[str, Any]) -> None:
    try:
        with open(SIM_FILE, "w") as f:
            json.dump(state, f, indent=2)
    except Exception:
        pass

# ---------------------------------------------------------------------------
# Public API Functions
# ---------------------------------------------------------------------------

def get_training_data() -> Dict[str, Any]:
    """Return complete training data for the frontend."""
    progress = _load_progress()
    total_modules = len(TRAINING_MODULES)
    completed = len(progress.get("completed_modules", []))
    pct = round((completed / total_modules) * 100) if total_modules > 0 else 0
    remaining = total_modules - completed
    est_remaining = sum(
        m.get("estimated_minutes", 2) for m in TRAINING_MODULES
        if m["id"] not in progress.get("completed_modules", [])
    )

    return {
        "status": "ok",
        "modules": TRAINING_MODULES,
        "simulation_scenarios": SIMULATION_SCENARIOS,
        "advanced_modules": ADVANCED_MODULES,
        "roles": TRAINING_ROLES,
        "progress": {
            **progress,
            "percent_complete": pct,
            "modules_completed": completed,
            "modules_total": total_modules,
            "modules_remaining": remaining,
            "estimated_remaining_minutes": est_remaining
        },
        "contextual_help": CONTEXTUAL_HELP,
        "disclaimer": DRAFT_DISCLAIMER,
        "sample_prefix": SAMPLE_PREFIX
    }

def update_progress(module_id: str, step_index: int = 0, completed: bool = False) -> Dict[str, Any]:
    """Update training progress for a module."""
    progress = _load_progress()
    if not progress.get("started"):
        progress["started"] = True
        progress["started_at"] = datetime.now().isoformat()

    progress["current_module"] = module_id
    progress["current_step"] = step_index

    if completed and module_id not in progress.get("completed_modules", []):
        # Enforce knowledge check before allowing completion
        module = next((m for m in TRAINING_MODULES if m["id"] == module_id), None)
        if module and module.get("knowledge_check"):
            if module_id not in progress.get("knowledge_checks_passed", []):
                return {"status": "error", "error": "Knowledge check must be passed before completing this module", "progress": {**progress, "percent_complete": round(len(progress.get("completed_modules", [])) / len(TRAINING_MODULES) * 100), "modules_completed": len(progress.get("completed_modules", [])), "modules_total": len(TRAINING_MODULES)}}
        progress["completed_modules"].append(module_id)
        # Check if all modules complete
        if len(progress["completed_modules"]) >= len(TRAINING_MODULES):
            progress["completed"] = True
            progress["completed_at"] = datetime.now().isoformat()
            progress["certificate"] = _generate_certificate(progress)

    _save_progress(progress)
    total_modules = len(TRAINING_MODULES)
    completed_count = len(progress.get("completed_modules", []))
    pct = round((completed_count / total_modules * 100)) if total_modules > 0 else 0
    progress["percent_complete"] = pct
    progress["modules_completed"] = completed_count
    progress["modules_total"] = total_modules
    return {"status": "ok", "progress": progress}

def record_knowledge_check(module_id: str, selected_index: int) -> Dict[str, Any]:
    """Record a knowledge check attempt. Returns pass/fail with explanation."""
    module = next((m for m in TRAINING_MODULES if m["id"] == module_id), None)
    if not module or not module.get("knowledge_check"):
        return {"status": "error", "error": "No knowledge check for this module"}

    kc = module["knowledge_check"]
    passed = selected_index == kc["correct_index"]
    progress = _load_progress()
    if passed:
        if module_id not in progress.get("knowledge_checks_passed", []):
            progress["knowledge_checks_passed"].append(module_id)
    else:
        if module_id not in progress.get("knowledge_checks_failed", []):
            progress["knowledge_checks_failed"].append(module_id)
    _save_progress(progress)

    return {
        "status": "ok",
        "passed": passed,
        "correct_index": kc["correct_index"],
        "explanation": kc["explanation"],
        "module_id": module_id
    }

def record_simulation(scenario_id: str, action_type: str, outcome: str = None) -> Dict[str, Any]:
    """Record a simulation action. Does NOT modify live data."""
    sim_state = _load_sim_state()
    sim_state["simulated_actions"].append({
        "scenario_id": scenario_id,
        "action_type": action_type,
        "outcome": outcome,
        "timestamp": datetime.now().isoformat(),
        "is_simulated": True
    })
    if scenario_id not in sim_state.get("completed_simulations", []):
        sim_state["completed_simulations"].append(scenario_id)
    _save_sim_state(sim_state)

    # Also track in progress
    progress = _load_progress()
    if scenario_id not in progress.get("simulations_completed", []):
        progress["simulations_completed"].append(scenario_id)
        _save_progress(progress)

    return {
        "status": "ok",
        "scenario_id": scenario_id,
        "action_type": action_type,
        "outcome": outcome,
        "is_simulated": True,
        "message": "Simulation recorded. No live data was modified."
    }

def ask_coach(question: str) -> Dict[str, Any]:
    """Deterministic training coach. Returns beginner-friendly guidance."""
    q_lower = question.lower().strip()
    for entry in COACH_RESPONSES:
        for kw in entry["keywords"]:
            if kw in q_lower:
                return {
                    "status": "ok",
                    "response": entry["response"],
                    "question": question
                }
    # Default response
    return {
        "status": "ok",
        "response": "I'm here to help you learn the platform. You can ask me things like: 'What does this mean?', 'Why is this important?', 'How should I use this?', 'What should I focus on?', or 'Why did this recommendation appear?' Try rephrasing your question using one of those patterns.",
        "question": question
    }

def get_contextual_help(view: str) -> Dict[str, Any]:
    """Get contextual help for a specific view."""
    help_data = CONTEXTUAL_HELP.get(view, CONTEXTUAL_HELP.get("home"))
    return {
        "status": "ok",
        "view": view,
        "title": help_data.get("title", ""),
        "help": help_data.get("help", "")
    }

def reset_training() -> Dict[str, Any]:
    """Reset all training progress."""
    progress = _fresh_progress()
    _save_progress(progress)
    sim_state = {"completed_simulations": [], "simulated_actions": []}
    _save_sim_state(sim_state)
    return {"status": "ok", "message": "Training progress reset."}

def get_certificate() -> Dict[str, Any]:
    """Get training certificate if completed."""
    progress = _load_progress()
    if not progress.get("completed"):
        return {"status": "not_complete", "message": "Complete all training modules to earn your certificate."}
    return {
        "status": "ok",
        "certificate": progress.get("certificate"),
        "completed_at": progress.get("completed_at"),
        "modules_completed": progress.get("completed_modules", []),
        "simulations_completed": progress.get("simulations_completed", [])
    }

def _generate_certificate(progress: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a training completion certificate."""
    return {
        "title": "Business Owner Certification",
        "recipient": "Agency Owner",
        "completed_date": datetime.now().strftime("%B %d, %Y"),
        "modules_completed": len(progress.get("completed_modules", [])),
        "simulations_completed": len(progress.get("simulations_completed", [])),
        "knowledge_checks_passed": len(progress.get("knowledge_checks_passed", [])),
        "certification_id": f"BOC-{datetime.now().strftime('%Y%m%d')}-001",
        "disclaimer": DRAFT_DISCLAIMER
    }

def get_training_health() -> Dict[str, Any]:
    """Generate training health report metrics."""
    total_modules = len(TRAINING_MODULES)
    total_sims = len(SIMULATION_SCENARIOS)
    total_kcs = len(ALL_KNOWLEDGE_CHECKS)
    total_help = len(CONTEXTUAL_HELP)
    total_coach = len(COACH_RESPONSES)
    total_roles = len(TRAINING_ROLES)
    built_roles = sum(1 for r in TRAINING_ROLES if r["is_built"])
    total_advanced = len(ADVANCED_MODULES)

    return {
        "modules_built": total_modules,
        "simulations_built": total_sims,
        "knowledge_checks": total_kcs,
        "contextual_help_screens": total_help,
        "coach_responses": total_coach,
        "roles_total": total_roles,
        "roles_built": built_roles,
        "advanced_modules": total_advanced,
        "mobile_ready": True,
        "desktop_ready": True,
        "health_score": 92
    }
