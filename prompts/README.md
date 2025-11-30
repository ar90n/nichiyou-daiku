# nichiyou-daiku LLMプロンプト

このディレクトリには、LLMを使ってnichiyou-daikuの設計コードを生成するためのプロンプトが含まれています。

## ファイル構成

```
prompts/
├── README.md           # このファイル
├── system.md           # システムプロンプト（LLMに最初に渡す）
├── user-template.md    # ユーザー入力テンプレート
└── examples/           # 記入例
    ├── side-table.md
    └── two-tier-shelf.md
```

## 使い方

### 1. システムプロンプトを設定

`system.md`の内容をLLMのシステムプロンプト（またはコンテキスト）として設定します。

### 2. ユーザー仕様を記入

`user-template.md`をコピーして、家具の仕様を記入します。

### 3. LLMに送信

記入した仕様をLLMに送信すると、NDスクリプトまたはPythonコードが生成されます。

## 例

### ChatGPT / Claude での使用

1. 新しい会話を開始
2. `system.md`の内容を最初のメッセージとして送信（または「これがシステムプロンプトです」と前置き）
3. 記入済みの仕様を送信
4. 生成されたコードを受け取る

### API での使用

```python
import anthropic  # または openai

system_prompt = open("prompts/system.md").read()
user_message = open("your-spec.md").read()

# Claude APIの例
client = anthropic.Anthropic()
response = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=4096,
    system=system_prompt,
    messages=[{"role": "user", "content": user_message}]
)
print(response.content[0].text)
```

## ヒント

- **出力形式**: シンプルな構造は`nd`、複雑な計算が必要な場合は`python`
- **寸法**: mmで正確に指定（概算でもOK、LLMが木材寸法を考慮して計算）
- **備考**: 特殊な要件や好みがあれば記載
