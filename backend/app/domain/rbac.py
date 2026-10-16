"""Who may do what. Access is decided by permissions, never by role names; a role is a named set of permissions.

The catalogue and the built-in roles are fixed here. Custom roles are rows in the store, checked by `validate`.
"""

import re
from dataclasses import dataclass

# code: (label, group). Order is the order the admin page lists them.
PERMISSIONS: dict[str, tuple[str, str]] = {
    "roles.manage": ("Create, edit and delete custom roles", "Administration"),
    "units.manage": ("Create, edit and import units, map unmapped sections", "Administration"),
    "policy.manage": ("Edit the review policy of a DISCOM", "Administration"),
    "accounts.manage": ("Create and edit staff accounts in own scope", "Administration"),
    "console.view": ("Department console summary", "Console"),
    "complaints.view": ("See the complaint inbox", "Complaints"),
    "complaints.reply": ("Reply to complaints and change their status", "Complaints"),
    "complaints.assign": ("Assign complaints", "Complaints"),
    "cases.view": ("See wrong reading cases in scope", "Bill review"),
    "cases.request_info": ("Ask the consumer for earlier bills, a meter photo or a note", "Bill review"),
    "cases.decide": ("Record a decision on a case", "Bill review"),
    "cases.reassign": ("Move a case to another account in scope", "Bill review"),
    "cases.approve": ("Approve or reject a decision awaiting approval", "Bill review"),
    "cases.mark_applied": ("Mark an approved revision as applied in billing", "Bill review"),
    "cases.export": ("Download revisions as CSV", "Bill review"),
    "consumer.unmask": ("See a full service number on an open case (audited)", "Bill review"),
    "audit.view": ("Audit log in scope", "Administration"),
    "chat.preview": ("Use the Assistant page as staff", "Console"),
    "self.bills": ("Own bills, chat and review requests", "Consumer"),
}

MONEY = frozenset({"cases.decide", "cases.approve", "cases.mark_applied"})
# Granting a role that carries one of these is reserved for roles.manage holders.
PRIVILEGED = frozenset({"roles.manage", "units.manage", "policy.manage"})
# Whoever manages roles never moves money, so roles.manage only sits with these.
ROLE_MANAGER_COMPANIONS = frozenset({"roles.manage", "units.manage", "policy.manage", "accounts.manage",
                                     "audit.view", "console.view"})


@dataclass(frozen=True)
class BuiltinRole:
    slug: str
    name: str
    description: str
    permissions: frozenset[str]


def _role(slug: str, name: str, description: str, *perms: str) -> BuiltinRole:
    return BuiltinRole(slug, name, description, frozenset(perms))


BUILTIN_ROLES: tuple[BuiltinRole, ...] = (
    BuiltinRole("super_admin", "Super admin", "Manages roles, units, policy and accounts. Never moves money.",
                frozenset(PERMISSIONS) - MONEY - {"self.bills"}),
    _role("admin", "Admin", "Manages staff accounts and reads the console and audit log.",
          "accounts.manage", "console.view", "complaints.view", "audit.view", "chat.preview"),
    _role("officer", "DISCOM officer", "Answers complaints and follows cases in scope.",
          "console.view", "complaints.view", "complaints.reply", "complaints.assign", "cases.view",
          "cases.request_info", "cases.reassign", "cases.export", "chat.preview"),
    _role("section_ae", "Section AE", "Reviews wrong reading cases for a section and decides them.",
          "console.view", "complaints.view", "complaints.reply", "cases.view", "cases.request_info", "cases.decide",
          "cases.reassign", "consumer.unmask"),
    _role("billing_approver", "Billing approver", "Approves decisions above the limit and marks revisions applied.",
          "cases.view", "cases.approve", "cases.mark_applied", "cases.export", "consumer.unmask"),
    _role("auditor", "Auditor", "Reads cases, exports and the audit log.",
          "console.view", "complaints.view", "cases.view", "cases.export", "audit.view"),
    _role("consumer", "Consumer", "A household using Bill Mitra for its own bills.", "self.bills"),
)
BUILTIN = {role.slug: role for role in BUILTIN_ROLES}
CONSUMER = "consumer"
SUPER_ADMIN = "super_admin"


def validate(permissions: list[str]) -> list[str]:
    """The cleaned permission list for a custom role, or ValueError saying what is wrong."""
    chosen = list(dict.fromkeys(permissions))
    unknown = [p for p in chosen if p not in PERMISSIONS]
    if unknown:
        raise ValueError(f"Unknown permission: {', '.join(unknown)}.")
    if not chosen:
        raise ValueError("A role needs at least one permission.")
    if "roles.manage" in chosen and not set(chosen) <= ROLE_MANAGER_COMPANIONS:
        extra = sorted(set(chosen) - ROLE_MANAGER_COMPANIONS)
        raise ValueError(f"roles.manage cannot be combined with {', '.join(extra)}.")
    return [p for p in PERMISSIONS if p in chosen]


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_")[:40]
    if not slug:
        raise ValueError("The role name needs at least one letter or digit.")
    return slug
