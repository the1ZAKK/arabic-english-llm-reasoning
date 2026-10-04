"""Load the human source quarantine without changing immutable source records."""
import json
from pathlib import Path
import re


DEFAULT_CATALOG = Path(__file__).with_name('source_quarantine.json')


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'Duplicate source quarantine field: {key}')
        result[key] = value
    return result


def _invalid_constant(value):
    raise ValueError(f'Invalid source quarantine JSON constant: {value}')


def load_quarantined_ids(path=None):
    """Missing catalog is compatible with old runs; malformed catalogs fail closed."""
    path = Path(path) if path is not None else DEFAULT_CATALOG
    try:
        raw = path.read_text(encoding='utf-8')
    except FileNotFoundError:
        return set()
    except (OSError, UnicodeError) as error:
        raise ValueError(f'Cannot read source quarantine catalog: {error}') from error
    try:
        catalog = json.loads(raw, object_pairs_hook=_unique_object, parse_constant=_invalid_constant)
    except (json.JSONDecodeError, ValueError) as error:
        raise ValueError(f'Malformed source quarantine catalog: {error}') from error
    if (not isinstance(catalog, dict) or type(catalog.get('schema_version')) is not int
            or catalog['schema_version'] != 1 or not isinstance(catalog.get('records'), list)):
        raise ValueError('Invalid source quarantine schema')
    seen, active_ids = set(), set()
    for entry in catalog['records']:
        if not isinstance(entry, dict):
            raise ValueError('Source quarantine entries must be objects')
        record_id = entry.get('id')
        if not isinstance(record_id, str) or not record_id.strip() or record_id != record_id.strip():
            raise ValueError('Source quarantine requires an unambiguous record ID')
        if record_id in seen:
            raise ValueError(f'Duplicate source quarantine record ID: {record_id}')
        seen.add(record_id)
        if type(entry.get('active')) is not bool:
            raise ValueError('Source quarantine active must be a boolean')
        for field in ('reason', 'reviewer'):
            if not isinstance(entry.get(field), str) or not entry[field].strip():
                raise ValueError(f'Source quarantine requires {field}')
        source_hash = entry.get('source_record_sha256')
        if not isinstance(source_hash, str) or re.fullmatch(r'[0-9a-f]{64}', source_hash) is None:
            raise ValueError('Source quarantine requires a valid source_record_sha256')
        if entry['active']:
            active_ids.add(record_id)
    return active_ids
