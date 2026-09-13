# Feature Spec Input: 5a93d29c-25e2-4aa5-be3f-0ed36ffa1aeb

**Originator**: U03QR8WKT29

**Request**: Add a GET /users/created-per-day endpoint that returns the number of users created on each of the last 7 days, oldest first.

## Product Documentation

**project_name**: User Creation Analytics API

**mode**: greenfield

**epics**: [{'id': 'EPIC-001', 'name': 'User Creation Statistics Endpoint', 'bounded_context': 'User Analytics', 'description': 'Provides a time-series endpoint that exposes the count of new user registrations per day for the most recent week.', 'features': [{'feature_id': 'FEAT-PO-001', 'title': 'GET /users/created-per-day endpoint', 'description': 'The system exposes a GET /users/created-per-day endpoint that returns a JSON response containing the number of users created on each of the last 7 days, ordered from oldest to newest. The response must include a list of date-count pairs covering the most recent 7-day window relative to the current date.', 'bounded_context': 'User Analytics', 'source_documents': ['request:GET /users/created-per-day endpoint that returns the number of users created on each of the last 7 days, oldest first'], 'constraints': ['Must return exactly 7 data points', 'Must order results oldest first', 'Must be a GET request'], 'suggested_context_files': [], 'depends_on': [], 'type': None, 'role': None, 'priority': None, 'moscow': None, 'value': None, 'complexity': None, 'acceptance_criteria': [], 'technical_notes': [], 'risks': [], 'open_questions': [], 'links': [], 'field_citations': {}}], 'source_documents': [], 'field_citations': {}}]

**priority_rationale**: This is a single-endpoint request with no external dependencies; the feature is self-contained and can be delivered as a standalone addition to the existing API surface.

**constraints_and_dependencies**: ['Endpoint must be stateless', 'Requires read access to user creation timestamps']

**open_questions**: ['What is the expected response format for the date-count pairs (e.g., ISO-8601 date strings, Unix timestamps)?', 'Should the endpoint return 0 for days with no new users, or omit those days?', 'What authentication/authorization is required for this endpoint?']

**feature_spec_inputs**: [{'feature_id': 'FEAT-PO-001', 'title': 'GET /users/created-per-day endpoint', 'description': 'The system exposes a GET /users/created-per-day endpoint that returns a JSON response containing the number of users created on each of the last 7 days, ordered from oldest to newest. The response must include a list of date-count pairs covering the most recent 7-day window relative to the current date.', 'bounded_context': 'User Analytics', 'source_documents': ['request:GET /users/created-per-day endpoint that returns the number of users created on each of the last 7 days, oldest first'], 'constraints': ['Must return exactly 7 data points', 'Must order results oldest first', 'Must be a GET request'], 'suggested_context_files': [], 'depends_on': [], 'type': None, 'role': None, 'priority': None, 'moscow': None, 'value': None, 'complexity': None, 'acceptance_criteria': [], 'technical_notes': [], 'risks': [], 'open_questions': [], 'links': [], 'field_citations': {}}]

**change_summary**: None

**coverage_score**: None

**source_documents**: []

**assumptions**: [{'id': 'ASM-001', 'category': 'domain', 'statement': 'The system records a creation timestamp for every user registration.', 'source': 'problem statement', 'confidence': 'high', 'impact_if_wrong': 'If creation timestamps are missing, the endpoint cannot calculate daily counts.'}, {'id': 'ASM-002', 'category': 'technical', 'statement': 'The API can query the user database for counts without significant performance impact.', 'source': 'problem statement', 'confidence': 'medium', 'impact_if_wrong': 'Large user tables may require optimized queries or caching to meet latency expectations.'}]

**estimate_unit**: None

