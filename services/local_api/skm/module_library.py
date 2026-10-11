"""Read-only provenance projection; it never declares a module executable."""


def from_snapshot(snapshot, catalog):
    facts = {n['id']: n for n in snapshot['nodes']}
    files = {f['id']: f for f in snapshot['files']}
    children = {nid: [] for nid in facts}
    for edge in snapshot['edges']:
        if edge['kind'] == 'contains':
            children[edge['source_id']].append(edge['target_id'])
    spans = {}
    for span in snapshot['spans']:
        spans.setdefault(span['node_id'], []).append(span)
    titles = {n['file_id']: n['title'] for n in snapshot['nodes'] if n['kind'] == 'file'}

    def descendants(nid):
        found = set()
        pending = [nid]
        while pending:
            current = pending.pop()
            if current in found:
                continue
            found.add(current)
            pending.extend(children[current])
        return found

    themes = [(n['title'], descendants(n['id'])) for n in snapshot['nodes'] if n['kind'] == 'theme']
    result = dict(catalog)
    nodes = []
    for item in catalog['nodes']:
        fact = facts[item['id']]
        if fact['skill_id'] != snapshot['skill']['id']:
            raise ValueError('模块来源身份不一致')
        original = spans.get(item['id'], [])
        if fact['file_id']:
            file_ids = [fact['file_id']]
        else:
            file_ids = sorted({facts[n]['file_id'] for n in descendants(item['id']) if facts[n]['file_id']})
        content = []
        for fid in file_ids:
            file = files[fid]
            exact = [s for s in original if s['file_id'] == fid]
            content.append({'file_id': fid, 'path': file['path'], 'title': titles.get(fid, file['path']),
                            'sha256': file['sha256'],
                            'ranges': [{'start_line': s['start_line'], 'end_line': s['end_line']} for s in exact]
                                      or ([{'start_line': 1, 'end_line': file['line_count']}] if file['line_count'] else [])})
        nodes.append({**item, 'source_skill_id': snapshot['skill']['id'],
                      'source_name': snapshot['skill']['name'], 'source_version': snapshot['skill']['version'],
                      'source_snapshot': catalog['snapshot'], 'source_content': content,
                      'source_groups': [title for title, ids in themes if item['id'] in ids],
                      'reuse_status': '待独立核验'})
    result['nodes'] = nodes
    return result


def combine(libraries):
    """A flat pool across declared sources, keeping same-named modules distinct."""
    sources = []
    nodes = []
    edges = []
    source_ids = set()
    node_ids = set()
    for library in libraries:
        sid = library['source_skill_id']
        if sid in source_ids:
            raise ValueError('重复来源身份，须先核对版本与冻结目录')
        source_ids.add(sid)
        sources.append({'id': sid, 'name': library['source_name'], 'version': library['version'],
                        'snapshot': library['snapshot'], 'module_count': len(library['nodes'])})
        for node in library['nodes']:
            if node['id'] in node_ids or node['source_skill_id'] != sid:
                raise ValueError('模块标识冲突或来源串接')
            node_ids.add(node['id'])
            nodes.append(node)
        edges.extend(library['contains'])
    return {'library_schema': 1, 'sources': sources, 'nodes': nodes, 'contains': edges,
            'module_count': len(nodes), 'review': '共享来源候选范围；独立复用条件尚待核验',
            # Compatibility for the single frozen-source draft backend. UI uses each node's own identity.
            'source_skill_id': sources[0]['id'] if len(sources) == 1 else None,
            'source_name': sources[0]['name'] if len(sources) == 1 else None,
            'version': sources[0]['version'] if len(sources) == 1 else None,
            'snapshot': sources[0]['snapshot'] if len(sources) == 1 else None}
