from cld._skeleton import healthcheck


def test_healthcheck():
    assert healthcheck() == "cld-ok"
