name: KO Haber Botu

on:
  schedule:
    - cron: "*/15 * * * *"
  workflow_dispatch:

permissions:
  contents: write

concurrency:
  group: haber-botu
  cancel-in-progress: false

jobs:
  kontrol:
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install requests beautifulsoup4
      - run: python haber_botu.py
        env:
          WEBHOOK_GUNCELLEME: ${{ secrets.WEBHOOK_GUNCELLEME }}
          WEBHOOK_HABERLER: ${{ secrets.WEBHOOK_HABERLER }}
      - name: Görülen haberleri kaydet
        run: |
          git config user.name "ko-haber-botu"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git add seen.json
          git diff --cached --quiet || (git commit -m "Görülen haberler güncellendi" && git push)
