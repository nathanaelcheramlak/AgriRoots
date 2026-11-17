"""Opt-in skills catalog fixtures in the disposable browser database only."""
from uuid import uuid4

from tests.test_connectors_rest import register, soil_spec, test_and_publish


def prepare_skills(client, office, origin):
    headers = office["users"]["admin"]["headers"]

    def create(manifest, enabled=False):
        r = client.post('/api/v1/skills', headers=headers, json=manifest)
        assert r.status_code == 201, r.text
        skill = r.json()
        if enabled:
            exact = {"version": skill["version"], "digest": skill["digest"], "request_key": uuid4().hex}
            r = client.post(f"/api/v1/skills/{skill['id']}/test", headers=headers, json=exact)
            assert r.status_code == 202, r.text
            r = client.post(f"/api/v1/skills/{skill['id']}/approve", headers=headers, json=exact)
            assert r.status_code == 200, r.text
            r = client.patch(f"/api/v1/skills/{skill['id']}/enabled", headers=headers, json={"enabled": True, "version": skill['version'], "expected_revision": r.json()['revision']})
            assert r.status_code == 200, r.text
        return skill

    create({"name": "skills_fixture_unavailable", "description": "Unconfirmed observations: missing approved field evidence", "instructions": "Use only approved evidence.", "required_capabilities": ["field.missing_fixture"], "optional_capabilities": ["rainfall.optional_fixture"]})
    create({"name": "skills_fixture_internal", "description": "Unsupported internal-action fixture", "instructions": "Fixture only.", "allowed_internal_actions": ["advisory.save_draft"]}, True)
    response = client.post('/api/v1/integrations', headers=headers, json={"name": "Skills dated fixture connection", "adapter_type": "rest", "base_url": origin, "egress_data_classes": ["public_environment", "plot_coordinates"]})
    assert response.status_code == 201, response.text
    conn = response.json()
    spec = soil_spec("skills_dated_evidence")
    spec['description'] = 'Explicit dated HTTP fixture evidence; not real rain observations.'
    spec['capability_tags'] = ['rainfall.fixture']
    spec['context_bindings'] = {"latitude": "plot.latitude", "longitude": "plot.longitude"}
    spec['input_json_schema']['properties'].update(start={"type": "string", "format": "date"}, end={"type": "string", "format": "date"})
    spec['input_json_schema']['required'] += ['start', 'end']
    tool = register(client, office, conn, spec)
    assert test_and_publish(client, office, conn, tool, {"start": "2025-07-01", "end": "2025-07-07"})['status'] == 'succeeded'
    create({"name": "skills_fixture_dates", "description": "Dated evidence fixture requiring start and end inputs", "instructions": "Use the controlled dated evidence fixture and explain its limitations.", "required_capabilities": ["rainfall.fixture"]}, True)
