from leadrouter.normalize import (
    clean_company, clean_domain, clean_state, company_key, domain_from_email, seniority,
)


def test_clean_domain_strips_scheme_www_and_path():
    assert clean_domain("https://www.Harborbrew.com/about?x=1") == "harborbrew.com"
    assert clean_domain("www.peakpantry.com") == "peakpantry.com"


def test_domain_from_email():
    assert domain_from_email("Sam@Peakpantry.com") == "peakpantry.com"
    assert domain_from_email("no-at-sign") == ""


def test_company_suffixes_removed():
    assert clean_company("Harbor Brew, Inc.") == "Harbor Brew"
    assert clean_company("Peak Pantry LLC") == "Peak Pantry"
    assert company_key("Peak Pantry, Co.") == company_key("peak pantry")


def test_state_names_become_codes():
    assert clean_state("new york") == "NY"
    assert clean_state("nj") == "NJ"


def test_seniority_first_match_wins():
    assert seniority("Founder & CEO") == "c_level"
    assert seniority("VP of Sales") == "vp"
    assert seniority("Head of Growth") == "head"
    assert seniority("Director, Retail Sales") == "director"
    assert seniority("Sales Operations Manager") == "manager"
    assert seniority("Account Executive") == "ic"
