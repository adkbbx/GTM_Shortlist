"""Built-to-order businesses are services, not product companies; product names with 'studio' stay products."""
import pytest

from shortlist.relevance import service_business


@pytest.mark.parametrize("title,service", [
    # Real titles from the saved eygentic.com run of 13 October ("Private AI B2B SaaS startups").
    ("Smeron | Custom AI Applications & B2B SaaS Growth Studio", True),
    ("BackOfficeBoss.ai — Custom AI automation built around your business", True),
    ("Acme | Bespoke workflow tools for logistics firms", True),
    ("Embedded iPaaS for B2B Software Companies | Prismatic", False),
    ("Siesta AI | Context-Native Enterprise AI Platform", False),
    ("HappyFox CRM Pricing | Plans for B2B SaaS Teams", False),
    ("Relay Studio | Onboarding analytics software", False),  # A product named Studio is not a services studio.
])
def test_built_to_order_work_reads_as_a_service(title, service):
    assert service_business(title) is service
