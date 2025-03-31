# ずんだもん対話システム

人が接近したらずんだもんキャラクターが反応して会話する対話システムです。Raspberry Piと各種センサー、VOICEVOXとOpenAI APIを使用して実装されています。

## 機能

- 超音波センサーによる人感知（距離に応じた反応）
- VOICEVOXによるずんだもんの音声合成
- OpenAI APIによる会話内容生成
- NewsAPIによるニュース検索と話題提供
- フルカラーLEDによる感情表現と口パク

## セットアップガイド

詳しいセットアップ方法や使用方法は [setup_guide.md](setup_guide.md) を参照してください。

## 必要なもの

- Raspberry Pi 3以上
- 超音波距離センサー（HC-SR04など）
- RGBフルカラーLED
- スピーカー
- VOICEVOXの実行環境
- OpenAI API キー
- NewsAPI キー

## システム設計図

- [状態遷移図](docs/state-diagram.md)
- [感情遷移フロー](docs/emotion-flow.md)
- [システムアーキテクチャ](docs/system-architecture.md)

## ファイル構成

- `zundamon_system.py` - メインのシステムコード
- `requirements.txt` - 必要なPythonライブラリ
- `setup_guide.md` - セットアップガイド
- `docs/` - 各種設計図とドキュメント

## ライセンス

MIT
