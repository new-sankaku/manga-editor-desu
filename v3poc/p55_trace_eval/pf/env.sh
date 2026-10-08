# P55 promptfoo 用の環境(source して使う)
export P55_LITELLM_KEY=sk-p55 PROMPTFOO_DISABLE_TELEMETRY=1 PROMPTFOO_DISABLE_UPDATE=1
S=/tmp/claude-0/-home-user-manga-editor-desu/fa704f96-c74d-4d28-a8d6-2b724e85a763/scratchpad
export PATH=$PATH:$S/pf_node/node_modules/.bin PROMPTFOO_CONFIG_DIR=$S/pf_cfg
export P55_EMPTY_DIR=$S/claude_empty P55_CALLS_LOG=$S/claude_calls.log
