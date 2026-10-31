from aria_driver import to_mp4


def make_recording(root, session, name):
    path = root / session / 'vrs' / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()


def test_newest_session_skips_sessions_without_a_recording(tmp_path):
    make_recording(tmp_path, '20261024T100000Z_aaaaaaaa', '2026-10-24-04:00:00.vrs')
    make_recording(tmp_path, '20261024T110000Z_bbbbbbbb', '2026-10-24-05:00:00.vrs')
    (tmp_path / '20261024T120000Z_cccccccc' / 'vrs').mkdir(parents=True)
    assert to_mp4.newest_session(tmp_path).name == '20261024T110000Z_bbbbbbbb'


def test_session_to_mp4_converts_each_recording_once(tmp_path, monkeypatch):
    make_recording(tmp_path, 'session', '2026-10-24-04:00:00.vrs')
    make_recording(tmp_path, 'session', '2026-10-24-04:05:00.vrs')
    output_dir = tmp_path / 'videos'
    output_dir.mkdir()
    (output_dir / 'session_2026-10-24-04-05-00.mp4').touch()
    converted = []
    monkeypatch.setattr(to_mp4, 'convert_vrs_to_mp4', lambda vrs, mp4: converted.append(mp4))
    mp4_paths = to_mp4.session_to_mp4(tmp_path / 'session', output_dir)
    assert [path.name for path in mp4_paths] == ['session_2026-10-24-04-00-00.mp4',
                                                 'session_2026-10-24-04-05-00.mp4']
    assert converted == [str(mp4_paths[0])]
