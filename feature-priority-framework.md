# Feature Priority Framework

## Goal

Build a lightweight internal product that helps teams submit, score, discuss, and rank feature requests without depending on Notion, spreadsheets, or paid third-party tools.

## Recommended MVP

The first version should do four things well:

1. Let teammates submit feature ideas in a consistent format.
2. Score each feature across a small set of priority dimensions.
3. Calculate a transparent priority score automatically.
4. Show ranked views for decision-making.

## Product Principles

- Keep the framework explainable. People should understand why a feature scored high or low.
- Separate raw inputs from the calculated priority score.
- Optimize for team trust, not mathematical perfection.
- Make it easy to update scores as context changes.
- Capture enough context to support discussion without turning submission into a chore.

## Core Data Model

Each feature should include:

- `title`
- `problem_statement`
- `proposed_solution`
- `request_source`
- `team_owner`
- `product_area`
- `status`
- `submitted_by`
- `created_at`
- `last_reviewed_at`

### Scoring fields

Use a 1-5 scale for each:

- `customer_impact`
- `strategic_fit`
- `urgency`
- `confidence`
- `effort`
- `dependency_risk`

### Supporting fields

- `urgency_reason`
- `notes`
- `quick_win`
- `dependencies`

## Suggested Scoring Formula

Start simple:

`priority_score = (customer_impact * 3) + (strategic_fit * 2) + (urgency * 2) + (confidence * 1) - (effort * 2) - (dependency_risk * 1) + (quick_win ? 2 : 0)`

This is not perfect, but it is:

- easy to explain
- easy to tune later
- hard to game accidentally

## Recommended Workflow

### 1. Submission

Anyone in the company can submit a feature request.

Required fields:

- title
- problem statement
- request source
- product area

### 2. Triage

A product owner or designated reviewer:

- removes duplicates
- rewrites vague submissions
- assigns owner and status
- decides whether the request is ready for scoring

### 3. Scoring

Product, engineering, and customer-facing teams score requests together or asynchronously.

Keep a short rubric visible next to the form so people score consistently.

### 4. Review

Use a ranked view in recurring roadmap reviews:

- highest score overall
- quick wins
- high urgency
- under-reviewed items

### 5. Decision

A feature can move to:

- backlog
- discovery
- planned
- in progress
- shipped
- rejected

## MVP Screens

### 1. Feature List

Shows all requests with:

- title
- product area
- status
- request source
- priority score
- effort
- urgency

### 2. Feature Detail

Shows:

- problem
- proposed solution
- scoring inputs
- auto-calculated score
- notes and rationale

### 3. New Feature Form

Simple internal submission form with validation.

### 4. Priority Dashboard

Shows:

- top ranked features
- quick wins
- by status
- by product area

## Best Technical Direction

If you want something cheap and company-owned, I would build this as:

- Frontend: `Next.js` or a simple server-rendered app
- Backend: lightweight API routes
- Database: `SQLite` for MVP, `Postgres` later if needed
- Auth: company SSO later, simple password or email allowlist first if internal-only
- Hosting: wherever you already host internal tools

If you want the absolute lowest-friction first version, you can even begin with:

- Vanilla HTML/CSS/JS frontend
- `localStorage` or a JSON file for prototyping
- then replace storage with a real database once the workflow feels right

## Build Order

### Phase 1

- Create data model
- Build submit form
- Build scoring form
- Show ranked list
- Auto-calculate score

### Phase 2

- Filters and saved views
- Notes and comments
- Review history
- Audit trail for score changes

### Phase 3

- SSO
- role-based permissions
- roadmap export
- Jira or internal handoff integration if needed later

## What To Avoid

- Too many scoring dimensions
- Overly clever formulas
- Making the first version look like a full project management system
- Allowing free-form inputs everywhere with no rubric

## Recommendation

The best path is to build a narrow internal app around one job:

"Help us decide which feature to work on next, with shared scoring and clear rationale."

That keeps scope under control and avoids rebuilding Notion badly.
