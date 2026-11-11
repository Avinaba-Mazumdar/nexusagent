from tests.db_guard import neon_endpoint


def test_neon_endpoint_pooled():
    url = "postgresql://u:p@ep-cool-river-a1b2c3-pooler.us-east-2.aws.neon.tech/neondb?sslmode=require"
    assert neon_endpoint(url) == "ep-cool-river-a1b2c3"


def test_neon_endpoint_direct():
    url = "postgresql://u:p@ep-cool-river-a1b2c3.us-east-2.aws.neon.tech/neondb?sslmode=require"
    assert neon_endpoint(url) == "ep-cool-river-a1b2c3"


def test_neon_endpoint_distinct_branch():
    url1 = "postgresql://u:p@ep-cool-river-a1b2c3.us-east-2.aws.neon.tech/neondb?sslmode=require"
    url2 = "postgresql://u:p@ep-quiet-lake-d4e5f6.us-east-2.aws.neon.tech/neondb?sslmode=require"
    assert neon_endpoint(url1) != neon_endpoint(url2)


def test_neon_endpoint_localhost():
    url = "postgresql://postgres:postgres@localhost:5432/nexus_test"
    assert neon_endpoint(url) == "localhost"
