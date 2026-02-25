from agent.tools.company_scorer import bant_score


def test_bant_scoring_basic():
    company = {
        "company_name": "TestCorp",
        "domain": "testcorp.com",
        "industry": "SaaS",
        "employee_count": 200,
        "estimated_revenue": 15000000,
        "funding_stage": "Series B",
        "tech_stack": ["AWS", "Python"],
    }
    icp = {
        "industries": ["SaaS"],
        "techStack": ["AWS", "Python"],
    }
    weights = {"budget": 0.3, "authority": 0.25, "need": 0.25, "timeline": 0.2}

    result = bant_score(company_profile=company, icp_profile=icp, bant_weights=weights)

    assert 0 <= result["budget"] <= 10
    assert 0 <= result["authority"] <= 10
    assert 0 <= result["need"] <= 10
    assert 0 <= result["timeline"] <= 10
    assert 0 <= result["total"] <= 10
    assert len(result["reasoning"]) > 0


def test_bant_scoring_minimal_data():
    company = {
        "company_name": "Unknown Corp",
        "domain": "unknown.com",
    }
    icp = {"industries": ["FinTech"]}
    weights = {"budget": 0.25, "authority": 0.25, "need": 0.25, "timeline": 0.25}

    result = bant_score(company_profile=company, icp_profile=icp, bant_weights=weights)

    assert result["budget"] == 3.0
    assert result["authority"] == 3.0
