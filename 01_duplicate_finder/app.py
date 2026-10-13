"""Find duplicate contents and copy files into an organized folder."""
import os
import sys
import filecmp
import hashlib
import shutil
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import Store, form, heading, note, table, run
store = Store(Path(__file__).with_name('data.json'), {'plan': []})
def scan(folder):
	root = Path(folder).expanduser().resolve()
	allowed = os.environ.get('DEMO_ROOT')
	if allowed:
		allowed_root = Path(allowed).expanduser().resolve()
		if root != allowed_root and allowed_root not in root.parents:
			raise ValueError('For the hosted demo, choose a folder inside the demo directory.')

	if not root.is_dir():
		raise ValueError('Enter an existing folder path.')
	groups = {}
	files = []
	for path in sorted(root.rglob('*')):
		if path.is_symlink() or not path.is_file():
			continue
		if '_organized' in path.relative_to(root).parts:
			continue
		digest = hashlib.sha256()
		with path.open('rb') as stream:
			for chunk in iter(lambda: stream.read(65536), b''):
				digest.update(chunk)
		key = (path.stat().st_size, digest.hexdigest())
		groups.setdefault(key, []).append(path)
		files.append(path)
	duplicates = []
	for (size, _), paths in groups.items():
		if len(paths) > 1:
			equal = [p for p in paths if filecmp.cmp(paths[0], p, shallow=False)]
			if len(equal) > 1:
				duplicates.append((size, equal))
	return root, files, duplicates
def build_plan(root, files):
	plan = []
	for index, source in enumerate(files, 1):
		category = source.suffix.lower().lstrip('.') or 'no_extension'
		target = root / '_organized' / category / f'{index}_{source.name}'
		plan.append([str(source), str(target)])
	return plan
def view():
	out = note('Enter a folder containing practice files. Originals are retained.')
	out += form('scan', [('folder', 'Full folder path', 'text', '')], 'Scan and preview')
	out += heading('Last organization preview')
	out += table(['Original', 'Proposed copy'], store.data['plan'])
	out += form('copy', [], 'Create organized copies')
	out += form('undo', [], 'Undo last copy operation')
	return out
def handle(data):
	if data['action'] == 'scan':
		if store.data.get('created'):
			raise ValueError('Undo the previous copy before preparing another plan.')
		root, files, duplicates = scan(data['folder'])
		store.data['plan'] = build_plan(root, files)
		store.save()
		rows = [(p.name, str(p), size) for size, paths in duplicates for p in paths]
		waste = sum(size * (len(paths) - 1) for size, paths in duplicates)
		return heading('Duplicate groups') + note(f'Redundant copies occupy {waste} bytes.') + table(['Name', 'Path', 'Bytes'], rows)
	if data['action'] == 'copy':
		if not store.data['plan'] or store.data.get('created'):
			raise ValueError('Prepare a new preview first, or undo the last copy.')
		for source, target in store.data['plan']:
			if not Path(source).is_file() or Path(target).exists():
				raise ValueError('A source is missing or a destination already exists.Scan again.')
		store.data['created'] = []
		store.save()
		for source, target in store.data['plan']:
			Path(target).parent.mkdir(parents=True, exist_ok=True)
			shutil.copy2(source, target)
			fingerprint = hashlib.sha256(Path(target).read_bytes()).hexdigest()
			store.data['created'].append({'path': target, 'hash': fingerprint})
			store.save()
		return note('Organized copies created. Original files have not been changed.')
	if data['action'] == 'undo':
		for entry in store.data.get('created', []):
			target = Path(entry['path'])
			if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() != entry['hash']:
				raise ValueError('A copied file was edited. Move it elsewhere before undoing.')
		for entry in store.data.get('created', []):
			Path(entry['path']).unlink(missing_ok=True)
		store.data['created'] = []
		store.data['plan'] = []
		store.save()
		return note('Copies removed. Empty category folders may remain.')
	raise ValueError('Unknown action.')
if __name__ == '__main__':
	run('Duplicate File Finder and Organizer', view, handle)

