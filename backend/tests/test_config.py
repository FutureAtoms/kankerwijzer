from app.config import Settings


def test_bundled_data_root_prefers_repo_local_problem_statement_data(tmp_path):
    team_root = tmp_path / "kankerwijzer"
    repo_local_data = team_root / "problem-statement" / "data"
    repo_local_data.mkdir(parents=True)

    settings = Settings(
        project_root=team_root / "backend" / "app",
        team_root=team_root,
        hackathon_root=tmp_path / "outer-hackathon",
    )

    assert settings.bundled_data_root == repo_local_data
    assert settings.kanker_dataset_path == repo_local_data / "kanker_nl_pages_all.json"
