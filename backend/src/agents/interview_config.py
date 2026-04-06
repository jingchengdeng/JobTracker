STT_MODEL = "gpt-4o-mini-transcribe"
TTS_MODEL = "gpt-4o-mini-tts"
TTS_DEFAULT_VOICE = "nova"
TTS_VOICES = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]

INTERVIEW_TYPES = ["behavioral", "technical", "system_design"]
DIFFICULTIES = ["easy", "medium", "hard"]
DURATIONS = [15, 30, 45, 60]

SESSION_STATUSES = ["planning", "active", "paused", "completed", "interrupted"]
TURN_ROLES = ["interviewer", "candidate"]

SCORING_DIMENSIONS = {
    "technical": [
        {"name": "Problem Solving", "description": "approach to breaking down problems, algorithmic thinking, handling edge cases"},
        {"name": "Technical Depth", "description": "mastery of relevant technologies, languages, frameworks mentioned in JD"},
        {"name": "System Thinking", "description": "understanding of how components interact, scalability, reliability considerations"},
        {"name": "Code Quality & Practices", "description": "testing, debugging approach, clean code principles, CI/CD awareness"},
        {"name": "Communication", "description": "clarity of technical explanations, ability to walk through thought process"},
    ],
    "behavioral": [
        {"name": "Leadership & Initiative", "description": "driving outcomes, taking ownership, influencing without authority"},
        {"name": "Collaboration & Teamwork", "description": "working across teams, resolving conflicts, supporting others"},
        {"name": "Problem Resolution", "description": "navigating ambiguity, handling setbacks, decision-making under pressure"},
        {"name": "Growth Mindset", "description": "learning from failure, seeking feedback, adapting to change"},
        {"name": "Communication", "description": "STAR structure, conciseness, tailoring message to audience"},
    ],
    "system_design": [
        {"name": "Requirements Gathering", "description": "clarifying scope, identifying constraints, asking the right questions"},
        {"name": "Architecture & Trade-offs", "description": "component decomposition, technology choices with justified reasoning"},
        {"name": "Scalability & Reliability", "description": "handling load, failure modes, redundancy, monitoring"},
        {"name": "Data Modeling", "description": "schema design, storage choices, consistency vs availability trade-offs"},
        {"name": "Communication", "description": "articulating design decisions, whiteboard clarity, structured walkthrough"},
    ],
}
