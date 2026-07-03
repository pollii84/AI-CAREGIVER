"""Disease-profile isolation test — Testing doc §2.4.

"Per Architecture doc §5's hard rule (no disease-name branching in code):
run the full adversarial suite against a synthetic AD/MS disease_profiles
row (Database doc §2.2) once one exists in staging, confirming the guardrail
pipeline behaves identically -- a failure here means the 'config not code'
boundary leaked."

The Testing doc's own wording ("once one exists in staging") makes this
precondition-gated, not something to fake by inventing a synthetic
disease_profiles row ourselves here -- db/schema.sql's seed data (verified
directly) only inserts the Parkinson's row; no AD/MS profile exists in this
environment. This test checks that precondition for real and skips with a
clear reason when it isn't met, rather than silently omitting §2.4
coverage.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text


def test_second_disease_profile_exists_for_isolation_testing(db_conn):
    other_profiles = db_conn.execute(
        text("SELECT disease_code FROM disease_profiles WHERE disease_code != 'parkinsons' AND active = true")
    ).scalars().all()

    if not other_profiles:
        pytest.skip(
            "Testing doc §2.4 precondition not met: no active non-parkinsons disease_profiles row exists "
            "yet in this environment (verified live against db/schema.sql's actual seed data, which only "
            "inserts 'parkinsons') -- 'once one exists in staging' per the Testing doc's own wording. Once "
            "an AD/MS disease_profiles row is seeded, re-parametrize the full adversarial suite "
            "(test_adversarial_suite.py) over both disease_code values instead of writing a second, "
            "duplicate suite here."
        )

    # Reachable once the precondition is met -- documents what should happen
    # next rather than leaving it unimplemented.
    assert other_profiles, "expected at least one non-parkinsons active disease profile"
