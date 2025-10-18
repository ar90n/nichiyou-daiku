# Visual Regression Tests

このディレクトリには、3D投影の視覚的回帰テストが含まれています。

## 概要

これらのテストは、生成されたPNG投影をベースライン画像と比較することで、
3Dモデル生成やレンダリングの意図しない変更を検出します。

## セットアップ

### 必要な依存関係

```bash
# build123d（3Dモデリング）
uv sync --all-extras

# 視覚的テスト依存（PNG変換と画像比較）
uv pip install cairosvg Pillow

# システムレベルの依存（Ubuntu/Debian）
sudo apt-get install libcairo2-dev
```

## テストの実行

```bash
# 全ての回帰テストを実行
pytest tests/regression/

# 特定のモデルのみテスト
pytest tests/regression/ -k corner_angle

# 詳細出力
pytest tests/regression/ -xvs
```

## ベースライン画像の管理

### 初期ベースライン生成

```bash
uv run python tests/regression/generate_baseline.py
```

### ベースライン更新

意図的な変更（機能追加、バグ修正など）の場合：

```bash
# 変更を確認
pytest tests/regression/ -xvs

# 問題なければベースラインを更新
uv run python tests/regression/generate_baseline.py

# 再度テスト
pytest tests/regression/
```

## テストケースの追加

### 1. 新しいfixtureを追加

```bash
mkdir tests/regression/fixtures/my_model
```

### 2. モデルファイルを作成

`tests/regression/fixtures/my_model/model.nd`:
```
// My model description
(piece1:2x4 =500)
(piece2:2x4 =500)

piece1 -[TF<0 BD<0]- piece2
```

### 3. ベースライン画像を生成

```bash
uv run python tests/regression/generate_baseline.py
```

これにより以下が生成されます：
- `my_model/top_view.png`
- `my_model/front_view.png`
- `my_model/side_view.png`

### 4. テストに追加

`tests/regression/test_projection_regression.py` の `@pytest.mark.parametrize` に追加：

```python
("my_model", "top_view", export_top_view),
("my_model", "front_view", export_front_view),
("my_model", "side_view", export_side_view),
```

### 5. テスト実行

```bash
pytest tests/regression/ -xvs
```

## トラブルシューティング

### テストが失敗する場合

1. **意図的な変更の場合**
   - ベースラインを更新: `uv run python tests/regression/generate_baseline.py`

2. **意図しない変更の場合**
   - コードを調査してバグを修正
   - build123dのバージョンを確認
   - 座標系の変更を確認

### 画像サイズの不一致

モデルの幾何形状が変更された可能性があります。
`tolerance`パラメータを調整するか、ベースラインを更新してください。

### 許容誤差の調整

`tests/utils/projection_utils.py` の `compare_images()` 関数で
`tolerance` パラメータ（デフォルト: 0.01）を調整できます。

## ファイル構成

```
tests/regression/
├── README.md                      # このファイル
├── conftest.py                   # pytest設定
├── generate_baseline.py          # ベースライン生成スクリプト
├── test_projection_regression.py # 回帰テスト
└── fixtures/                     # テストデータ
    ├── corner_angle/
    │   ├── model.nd              # モデル定義
    │   ├── top_view.png          # ベースライン画像
    │   ├── front_view.png
    │   └── side_view.png
    └── shelf/
        ├── model.nd
        ├── top_view.png
        ├── front_view.png
        └── side_view.png
```
