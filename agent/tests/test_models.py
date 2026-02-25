from models import ICPProfile, BANTWeights, BANTScore, Lead


def test_icp_profile_parsing():
    data = {
        "industries": ["SaaS"],
        "companySizeRange": {"min": 50, "max": 500},
        "revenueRange": {"min": 1000000, "max": 50000000},
        "geographies": ["US"],
        "techStack": ["AWS"],
        "keywords": [],
        "additionalNotes": "",
    }
    icp = ICPProfile(**data)
    assert icp.industries == ["SaaS"]
    assert icp.company_size_range["min"] == 50


def test_bant_weights():
    w = BANTWeights(budget=0.3, authority=0.25, need=0.25, timeline=0.2)
    assert w.budget == 0.3
    assert abs(w.budget + w.authority + w.need + w.timeline - 1.0) < 0.01


def test_lead_model():
    lead = Lead(
        companyName="Acme",
        domain="acme.com",
        industry="SaaS",
        bantScore=BANTScore(
            budget=8.0,
            authority=7.0,
            need=9.0,
            timeline=6.0,
            total=7.65,
            reasoning="Test reasoning",
        ),
    )
    assert lead.company_name == "Acme"
    assert lead.bant_score.total == 7.65
