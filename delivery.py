"""Delivery receipts shared by the primary send and its 15-minute watchdog."""
import hashlib
import io
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
import zipfile

CHANNEL_ID = -1003705572727
ARTIFACT_NAME = 'FLS-QT-Delivery-Receipts'


def fingerprint(path, caption):
    return hashlib.sha256(Path(path).read_bytes() + b'\0' + caption.encode('utf-8')).hexdigest()


def find_receipt(report, digest):
    import requests
    token = os.environ.get('GITHUB_TOKEN')
    repo = os.environ.get('GITHUB_REPOSITORY')
    if not token or not repo:
        raise SystemExit('Missing GitHub receipt lookup credentials; no duplicate send attempted.')
    headers = {'Authorization': f'Bearer {token}', 'Accept': 'application/vnd.github+json'}
    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    try:
        response = requests.get(f'https://api.github.com/repos/{repo}/actions/artifacts',
                                headers=headers, params={'name': ARTIFACT_NAME, 'per_page': 100},
                                timeout=(15, 30))
        response.raise_for_status()
        for artifact in response.json()['artifacts']:
            if artifact.get('expired') or artifact['created_at'] < cutoff:
                continue
            archive = requests.get(artifact['archive_download_url'], headers=headers, timeout=(15, 60))
            archive.raise_for_status()
            with zipfile.ZipFile(io.BytesIO(archive.content)) as bundle:
                for name in bundle.namelist():
                    if name.endswith('.receipt.json'):
                        receipt = json.loads(bundle.read(name))
                        if (receipt.get('report') == report and receipt.get('digest') == digest
                                and receipt.get('chat_id') == CHANNEL_ID and receipt.get('message_id')):
                            return receipt
    except (requests.RequestException, ValueError, KeyError, zipfile.BadZipFile):
        raise SystemExit('Could not verify prior Telegram receipts; no unverified duplicate sent.') from None
    return None


def deliver(path, caption, send_photo):
    path = Path(path)
    digest = fingerprint(path, caption)
    receipt = find_receipt(path.stem, digest)
    if receipt:
        print(f"Already delivered: {path.stem}; channel: {receipt['chat_id']}; message_id: {receipt['message_id']}")
    else:
        message = send_photo(path, caption)
        receipt = {'report': path.stem, 'digest': digest, 'chat_id': message['chat_id'],
                   'message_id': message['message_id'], 'confirmed_at': datetime.now(timezone.utc).isoformat()}
        if receipt['chat_id'] != CHANNEL_ID or not receipt['message_id']:
            raise SystemExit('Delivery receipt has an invalid destination or message ID.')
    path.with_suffix('.receipt.json').write_text(json.dumps(receipt, ensure_ascii=False), encoding='utf-8')
    return receipt
