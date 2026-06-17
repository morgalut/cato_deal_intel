# Skill: Human-in-the-Loop Approval Routing

Purpose: prevent high-impact AI recommendations from becoming customer-facing actions without approval.

Triggers:
- discount > 10% => Deal Desk
- discount > 15% => Deal Desk + Sales Leader
- liability/data retention/security-specific customer language => Legal
- low confidence/conflicting evidence/missing data => Human Reviewer
- customer-facing concession language => blocked until approved

Outputs:
- approval_required: boolean
- approval_types: list
- customer_facing_allowed: boolean
- status: pending / approved / rejected / not_required
