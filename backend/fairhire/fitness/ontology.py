"""Deterministic skill/term ontology for NER-style matching.

Every term is matched as a *literal variant* (word-boundary, case-insensitive)
against the raw document so that character offsets stay accurate for the
frontend "matching lines" visualization. No LLM, no embeddings.

For single-word terms, the canonical form must be long enough (>3 chars) to
avoid false positives on ordinary words (e.g. "Go" the verb vs the language).
"""

from __future__ import annotations

from dataclasses import dataclass

CATEGORY_LABELS = {
    "language": "Language",
    "framework": "Framework / library",
    "frontend": "Frontend",
    "backend": "Backend",
    "mobile": "Mobile",
    "database": "Database",
    "cloud": "Cloud",
    "devops": "DevOps / tooling",
    "data": "Data",
    "ml": "ML / AI",
    "methodology": "Method / practice",
    "domain": "Domain",
    "tool": "Tool",
}


@dataclass(frozen=True)
class OntologyTerm:
    canonical: str
    variants: tuple[str, ...]
    category: str


def _t(canonical: str, category: str, *variants: str) -> OntologyTerm:
    """Build an ontology entry. Variants are literal strings as they appear in text."""
    return OntologyTerm(canonical=canonical, variants=variants or (canonical,), category=category)


_TERMS: list[OntologyTerm] = [
    # ---- Languages ----
    _t("Python", "language", "Python", "py"),
    _t("JavaScript", "language", "JavaScript", "Javascript", "JS", "ES6", "ES2015"),
    _t("TypeScript", "language", "TypeScript", "Typescript", "TS"),
    _t("Java", "language", "Java"),
    _t("C++", "language", "C++", "C plus plus", "CPP"),
    _t("C#", "language", "C#", "Csharp"),
    _t("Golang", "language", "Golang", "GoLang", "Go language"),
    _t("Rust", "language", "Rust"),
    _t("Ruby", "language", "Ruby"),
    _t("Swift", "language", "Swift"),
    _t("Kotlin", "language", "Kotlin"),
    _t("PHP", "language", "PHP"),
    _t("Scala", "language", "Scala"),
    _t("SQL", "language", "SQL"),
    _t("HTML", "language", "HTML", "HTML5"),
    _t("CSS", "language", "CSS", "CSS3"),
    _t("Bash", "language", "Bash", "Bash scripting"),
    _t("Perl", "language", "Perl"),
    _t("MATLAB", "language", "MATLAB", "Matlab"),
    _t("Dart", "language", "Dart"),
    _t("Groovy", "language", "Groovy"),
    _t("Elixir", "language", "Elixir"),
    _t("Clojure", "language", "Clojure"),
    _t("Haskell", "language", "Haskell"),
    _t("Lua", "language", "Lua"),
    _t("Objective-C", "language", "Objective-C", "Objective C", "ObjectiveC"),
    _t("Julia", "language", "Julia"),
    _t("PowerShell", "language", "PowerShell", "Powershell"),
    _t("R", "language", "R statistical", "R programming", "R language"),

    # ---- Frontend / frameworks ----
    _t("React", "framework", "React", "React.js", "Reactjs"),
    _t("React Native", "frontend", "React Native", "ReactNative"),
    _t("Angular", "framework", "Angular", "AngularJS", "Angular.js"),
    _t("Vue", "framework", "Vue", "Vue.js", "Vuejs"),
    _t("Svelte", "framework", "Svelte"),
    _t("Next.js", "framework", "Next.js", "Nextjs"),
    _t("Nuxt", "framework", "Nuxt", "Nuxt.js"),
    _t("Node.js", "backend", "Node.js", "Nodejs"),
    _t("Express", "backend", "Express", "Express.js", "ExpressJS"),
    _t("Django", "backend", "Django"),
    _t("Flask", "backend", "Flask"),
    _t("FastAPI", "backend", "FastAPI", "Fast Api"),
    _t("Rails", "backend", "Ruby on Rails", "Rails"),
    _t("Spring Boot", "backend", "Spring Boot", "SpringBoot"),
    _t("Spring", "backend", "Spring", "Spring Framework"),
    _t("ASP.NET", "backend", "ASP.NET", "ASP Net", "AspNet"),
    _t(".NET", "backend", ".NET", ".Net", "Dotnet"),
    _t("Laravel", "backend", "Laravel"),
    _t("Symfony", "backend", "Symfony"),
    _t("GraphQL", "backend", "GraphQL", "Graph QL"),
    _t("gRPC", "backend", "gRPC"),
    _t("REST", "backend", "REST", "RESTful", "REST API", "REST APIs"),
    _t("Redux", "frontend", "Redux"),
    _t("MobX", "frontend", "MobX", "Mobx"),
    _t("jQuery", "frontend", "jQuery", "Jquery"),
    _t("Bootstrap", "frontend", "Bootstrap"),
    _t("Tailwind CSS", "frontend", "Tailwind CSS", "Tailwind"),
    _t("WebSocket", "backend", "WebSocket", "Web Sockets", "Websockets"),
    _t("HTML/CSS", "frontend", "HTML/CSS", "HTML and CSS", "HTML & CSS"),

    # ---- Data / ML / AI ----
    _t("Machine Learning", "ml", "Machine Learning", "Machine-learning", "ML"),
    _t("Deep Learning", "ml", "Deep Learning", "Deep-learning", "DL"),
    _t("TensorFlow", "ml", "TensorFlow", "Tensorflow"),
    _t("PyTorch", "ml", "PyTorch", "Pytorch", "Torch"),
    _t("Keras", "ml", "Keras"),
    _t("scikit-learn", "ml", "scikit-learn", "scikit learn", "sklearn"),
    _t("pandas", "data", "pandas", "Pandas"),
    _t("NumPy", "data", "NumPy", "Numpy"),
    _t("Spark", "data", "Apache Spark", "Spark"),
    _t("Hadoop", "data", "Hadoop", "Apache Hadoop"),
    _t("Kafka", "data", "Apache Kafka", "Kafka"),
    _t("Airflow", "data", "Airflow", "Apache Airflow"),
    _t("Databricks", "data", "Databricks"),
    _t("MLflow", "ml", "MLflow", "ML Flow"),
    _t("Hugging Face", "ml", "Hugging Face", "HuggingFace", "Huggingface"),
    _t("LangChain", "ml", "LangChain", "Langchain"),
    _t("RAG", "ml", "RAG", "Retrieval-Augmented Generation", "Retrieval Augmented Generation"),
    _t("LLM", "ml", "LLM", "LLMs", "Large Language Model", "Large Language Models"),
    _t("OpenAI", "ml", "OpenAI"),
    _t("Computer Vision", "ml", "Computer Vision", "Computer-vision"),
    _t("NLP", "ml", "NLP", "Natural Language Processing"),
    _t("Data Engineering", "data", "Data Engineering", "Data engineering"),
    _t("Data Science", "data", "Data Science", "Data science"),
    _t("Data Analysis", "data", "Data Analysis", "Data analytics", "Analytics"),
    _t("ETL", "data", "ETL"),
    _t("Feature Engineering", "ml", "Feature Engineering", "Feature engineering"),
    _t("Recommendation Systems", "ml", "Recommendation Systems", "Recommendation Systems", "Recommender Systems", "Recommendation engine"),
    _t("Time Series", "ml", "Time Series", "Time-series"),
    _t("Anomaly Detection", "ml", "Anomaly Detection", "Anomaly detection"),
    _t("Data Visualization", "data", "Data Visualization", "Visualization", "Visualizations", "Dashboards"),

    # ---- Databases ----
    _t("PostgreSQL", "database", "PostgreSQL", "Postgres"),
    _t("MySQL", "database", "MySQL", "My SQL"),
    _t("SQLite", "database", "SQLite"),
    _t("MongoDB", "database", "MongoDB", "Mongo"),
    _t("Redis", "database", "Redis"),
    _t("Cassandra", "database", "Cassandra", "Apache Cassandra"),
    _t("DynamoDB", "database", "DynamoDB", "Dynamo DB"),
    _t("Elasticsearch", "database", "Elasticsearch", "Elastic Search"),
    _t("Snowflake", "database", "Snowflake"),
    _t("BigQuery", "database", "BigQuery", "Big Query"),
    _t("Redshift", "database", "Redshift", "Amazon Redshift"),
    _t("ClickHouse", "database", "ClickHouse", "Click House"),
    _t("Neo4j", "database", "Neo4j"),
    _t("Oracle", "database", "Oracle"),
    _t("MariaDB", "database", "MariaDB"),
    _t("Data Warehouse", "database", "Data Warehouse", "Data warehouse", "Warehouse"),
    _t("Data Lake", "database", "Data Lake", "Data lake"),
    _t("Vector Database", "database", "Vector Database", "Vector Databases", "Vector store", "Vector stores"),

    # ---- Cloud / DevOps ----
    _t("AWS", "cloud", "AWS", "Amazon Web Services"),
    _t("Azure", "cloud", "Azure", "Microsoft Azure"),
    _t("GCP", "cloud", "GCP", "Google Cloud", "Google Cloud Platform"),
    _t("Docker", "devops", "Docker"),
    _t("Kubernetes", "devops", "Kubernetes", "K8s", "K8S"),
    _t("Terraform", "devops", "Terraform"),
    _t("Ansible", "devops", "Ansible"),
    _t("Jenkins", "devops", "Jenkins"),
    _t("GitHub Actions", "devops", "GitHub Actions", "Github Actions", "GH Actions"),
    _t("GitLab CI", "devops", "GitLab CI", "Gitlab CI", "GitLab CI/CD", "Gitlab CI/CD"),
    _t("CircleCI", "devops", "CircleCI", "Circle CI"),
    _t("Helm", "devops", "Helm"),
    _t("Prometheus", "devops", "Prometheus"),
    _t("Grafana", "devops", "Grafana"),
    _t("Datadog", "devops", "Datadog"),
    _t("New Relic", "devops", "New Relic"),
    _t("nginx", "devops", "nginx", "NGINX", "Nginx"),
    _t("Linux", "devops", "Linux"),
    _t("CI/CD", "devops", "CI/CD", "Continuous Integration", "Continuous Delivery", "Continuous Deployment"),
    _t("Git", "devops", "Git"),
    _t("GitHub", "devops", "GitHub", "Github"),
    _t("GitLab", "devops", "GitLab", "Gitlab"),
    _t("Containers", "devops", "Containers", "Containerization"),
    _t("Serverless", "cloud", "Serverless", "server-less"),
    _t("Microservices", "backend", "Microservices", "Micro-services", "Micro service", "Micro services"),

    # ---- Mobile ----
    _t("Android", "mobile", "Android"),
    _t("iOS", "mobile", "iOS", "IOS"),
    _t("Flutter", "mobile", "Flutter"),
    _t("Xamarin", "mobile", "Xamarin"),
    _t("Expo", "mobile", "Expo"),
    _t("Mobile Development", "mobile", "Mobile Development", "Mobile apps", "Mobile applications"),

    # ---- Methods / practices ----
    _t("Agile", "methodology", "Agile"),
    _t("Scrum", "methodology", "Scrum"),
    _t("Kanban", "methodology", "Kanban"),
    _t("TDD", "methodology", "TDD", "Test-Driven Development", "Test Driven Development"),
    _t("System Design", "methodology", "System Design", "Systems Design", "System architecture", "Systems architecture"),
    _t("Distributed Systems", "methodology", "Distributed Systems", "Distributed systems", "Distributed computing", "Distributed services", "Distributed platforms", "Distributed infrastructure"),
    _t("Software Engineering", "domain", "Software Engineering", "Software engineering", "Software Engineer", "Software Developer", "Software Development", "Software development"),
    _t("Full-stack", "domain", "Full-stack", "Fullstack", "Full Stack"),
    _t("Front-end", "frontend", "Front-end", "Frontend", "Front end"),
    _t("Back-end", "backend", "Back-end", "Backend", "Back end"),
    _t("API Development", "backend", "API Development", "API Design", "APIs", "API"),
    _t("OOP", "methodology", "Object-Oriented Programming", "OOP", "Object oriented"),
    _t("Functional Programming", "methodology", "Functional Programming", "Functional programming"),
    _t("Design Patterns", "methodology", "Design Patterns", "Software design patterns"),
    _t("Unit Testing", "methodology", "Unit Testing", "Unit tests", "Unit testing", "Unit test"),
    _t("Integration Testing", "methodology", "Integration Testing", "Integration tests"),
    _t("Test Automation", "methodology", "Test Automation", "Automated Testing", "Automated tests"),
    _t("QA", "methodology", "Quality Assurance", "QA"),
    _t("Security", "domain", "Security", "Cybersecurity", "Cyber Security", "Application Security", "AppSec", "Security Engineering"),
    _t("Cryptography", "domain", "Cryptography"),
    _t("Networking", "domain", "Network Engineering", "Computer Networking"),
    _t("SRE", "domain", "Site Reliability", "SRE", "Reliability Engineering", "Reliability Engineer"),
    _t("Accessibility", "domain", "Accessibility", "A11y"),
    _t("High Availability", "domain", "High Availability", "High-availability"),
    _t("Observability", "devops", "Observability", "Monitoring", "Logging", "Tracing"),
    _t("Performance Engineering", "domain", "Performance Engineering", "Performance Optimization", "Performance tuning"),
    _t("Web Development", "domain", "Web Development", "Web applications", "Web apps"),

    # ---- Tools ----
    _t("Jira", "tool", "Jira", "JIRA"),
    _t("Confluence", "tool", "Confluence"),
    _t("Figma", "tool", "Figma"),
    _t("Postman", "tool", "Postman"),
    _t("Swagger", "tool", "Swagger", "OpenAPI"),
    _t("Notion", "tool", "Notion"),
]

_CANONICAL_TO_TERM: dict[str, OntologyTerm] = {t.canonical: t for t in _TERMS}

# Variant (lowercased) -> canonical. First variant wins; longer variants preferred
# so "React Native" beats "React" when both could apply at the same spot.
_VARIANT_INDEX: dict[str, str] = {}
for _t_ in _TERMS:
    for _v in _t_.variants:
        key = _v.lower()
        existing = _VARIANT_INDEX.get(key)
        if existing is None or len(_v) > len(_t_.canonical):
            _VARIANT_INDEX[key] = _t_.canonical


def all_terms() -> list[OntologyTerm]:
    return list(_TERMS)


def terms_by_category() -> dict[str, list[OntologyTerm]]:
    grouped: dict[str, list[OntologyTerm]] = {}
    for t in _TERMS:
        grouped.setdefault(t.category, []).append(t)
    return grouped


def category_label(category: str) -> str:
    return CATEGORY_LABELS.get(category, category.title())
