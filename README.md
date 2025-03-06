# taskhub

## 重要なメモ

- 現状各リクエスト内は直列に処理している  
  → テストケースが複数ある場合、１つ１つ処理する。なので、テストケースが多いと実行に時間がかかる。

- 現状、実行用コンテナはコールドスタートのみ  
  → 実行の都度起動するので、その分時間がかかる  
  ※ これとは関係なく、初めて利用するコンテナイメージの場合はコンテナイメージの取得時間もかかる。

- 課題ファイルはgithubで管理する
  - https://github.com/obeh29380/taskhub-problems.git
  - アプリ起動時に読み込み、オンメモリで持つ
  - テストコードはメモリに持ちたくないため、実行の度に読み取る

## 起動方法

### 共通事項

dockerが使用できる環境で、シェルスクリプトが実行できれば良いです。  
windowsの場合、wslなどを利用してください。  
なお、ブラウザから利用する場合、デフォルトでは、外部から80番ポートへのアクセスが可能な環境が必要です。  
起動スクリプトの引数で、ホストマシン側のポートは指定可能です。  


### シングルノードもしくはswarmクラスタ作成済みの環境にデプロイする場合

以下のコマンドでコンテナイメージのビルドとコンテナの起動を行います。  
すでにコンテナ起動済みの場合、新しくビルドしたイメージで再構築を行います。  
swarmクラスタ作成済みの環境にデプロイする場合は、以下をmanagerノード上で実行してください。  

```
bash run.sh
```

### シングルノード上でswarmクラスタの検証を行う場合（２コンテナで起動: dind, swarm）

単一ノード上で、複数ノードでのクラスタを仮想的に作成します。  
検証用を想定した環境です。  

#### 1. dind環境作成  

  dind(docker in docker)を利用し、Dockerコンテナを起動できるDockerコンテナを起動します。  
  コンテナは２つ（manager, worker）起動します。  
  以下のコマンドで起動します。`port`は、指定しない場合`80`番になります。  

    $ bash tests/run_dind.sh [port]

#### 2. アプリケーションコンテナの起動  

  起動したDockerコンテナ上に、アプリケーションコンテナを起動します。  

    $ docker exec taskhub-manager bash run.sh
