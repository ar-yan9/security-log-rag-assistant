"""Conservative exact-address constraints, not an entity parser or query language."""
import ipaddress
import re

# Boundaries avoid treating parts of identifiers, malformed addresses or CIDRs
# as exact address literals. CIDR/range queries are outside this helper's scope.
TOKEN = re.compile(r'(?<![\w.:/])(?:[0-9A-Fa-f]*:[0-9A-Fa-f:.]+|(?:\d{1,3}\.){3}\d{1,3})(?![\w:/]|\.\w)')


def addresses(text):
    found = set()
    for match in TOKEN.finditer(text):
        token = match.group().rstrip('.')
        # A sentence's final period is punctuation, not part of an address.
        try:
            found.add(str(ipaddress.ip_address(token)))
        except ValueError:
            pass
    return found


def eligible_ids(question, records):
    """Require every valid address literal in the question in a single event.

    Multiple addresses use AND, not OR. This can miss cross-event or OR results.
    It does not interpret negation, CIDRs, ranges, IP:port pairs or usernames.
    """
    required = addresses(question)
    if not required:
        return None
    return {r['id'] for r in records if required <= addresses(r['text'])}
