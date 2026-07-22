AGENT_EMAIL_LITERAL_ALLOWED_DOMAINS = frozenset({
    "openai.com",
    "anthropic.com",
    "cursor.com",
    "cursor.sh",
    "google.com",
    "google.dev",
    "github.com",
    "microsoft.com",
    "azure.com",
    "perplexity.ai",
    "x.ai",
    "coderabbit.ai",
    "mistral.ai",
    "deepseek.com",
    "cohere.com",
    "meta.com",
    "sourcegraph.com",
    "devin.ai",
    "codeium.com",
    "kimi.ai",
    # RFC 2606 / documentation fixtures only. Do not add personal mail domains.
    "example.invalid",
    "example.com",
    "example.org",
    "example.net",
    "localhost",
})
# RFC 1918 private IPv4 ranges — graduated lesson candidates may contain
# these as operational evidence (e.g. DHCP drift, LAN peer addresses).
# Exempt ONLY .agent/memory/candidates/graduated/*.json from topology-token
# scanning for these patterns; all other .agent guards remain in force.
_RFC1918_PRIVATE_IP_RE = re.compile(
    r"(?:"
    r"\b10\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"          # 10.0.0.0/8
    r"|\b172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}\b"  # 172.16-31.0.0/12
    r"|\b192\.168\.\d{1,3}\.\d{1,3}\b"          # 192.168.0.0/16
    r")"
)
_GENERATED_ARTIFACT_PATTERNS = (