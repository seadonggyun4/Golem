# Styxis installation entry / 설치 진입점

[Styxis Plugin](https://github.com/seadonggyun4/styxis-plugin#install) is the user-facing installation entry. Golem owns its native engine, MCP runtime, permissions and packages.

사용자 설치 진입점은 Styxis로 통일합니다. 설치만으로 native·runtime·프로젝트 권한을 만들지 않습니다.

```text
Styxis Plugin: choose pinned Golem / 고정된 Golem 선택
  → client package / client별 패키지
  → Golem Setup: review exact local launcher / 정확한 로컬 launcher 검토
  → existing native and policy checks / 기존 native·정책 검사
  → tools permitted for that client / 해당 client에 허용된 도구
```

| Client | Entry and setup / 진입·설정 |
| --- | --- |
| Codex | `golem@styxis-plugin` → Golem Setup → reviewed launcher. [Setup](integration-codex-plugin.md) |
| Claude Code | `golem@styxis-plugin` → Golem Setup with a separately reviewed launcher. The adapter uses `CLAUDE_PLUGIN_ROOT`. |
| Claude Desktop | Styxis Desktop download → reviewed MCPB → select that client's private adapter state directory. This is not a Claude Code plugin. [Desktop guide](integration-mcpb.md) |

Codex, Claude Code, portable and Claude Desktop adapters use separate approval records. Installation does not import another client's launcher approval, renew an expired Intent observation, change producer pins, display an Owner window, or authorize a Work action.

각 client의 승인 기록은 분리합니다. Desktop의 `golem-prepare` 이름은 기존 extension identity를 유지하기 위한 것으로, 공개 launcher 연결 패키지의 권한은 기존 launcher·정책이 결정합니다. 기존 기능별 MCPB의 profile 권한 계약을 자동 이전하지 않습니다.

## Setup and migration / 설정·전환

1. Verify the catalog's exact source SHA and package inventory. For Desktop, verify the linked archive SHA as well. Product code stays in Golem.
2. Review an owner-private JSON containing only the existing launcher's absolute `command` and string `args`. Preserve its runtime·native·producer·policy pins.
3. Configure the installed adapter with the exact reviewed JSON digest and the intended `--client`: `codex`, `claude-code`, `portable`, or `claude-desktop`. The Desktop state path must match its Configure selection. This records launcher selection, not native action approval.
4. Preserve recovery files and use official removal/update paths to leave one verified Golem connection per client. Existing private launcher-only packages must not silently import adapter state.
5. Confirm installation, handshake, tool definitions and authorized calls separately. Existing Work execution HOLD, approvals, Work, evidence and `COMMIT_UNKNOWN` remain in force. Expired observation contracts require separate renewal; a reinstall does not renew them.

기존 Golem 저장소 카탈로그는 신규 배포 항목 없는 호환 표식입니다. Owner 전용 private marketplace 생성기는 유지보수·격리 검증에만 사용합니다. Styxis 등록은 공개된 정확한 commit의 전체 plugin inventory를 검사한 뒤 진행하며 미게시 변경을 과거 SHA에 붙이지 않습니다.

공개 Desktop 패키지 생성은 `python3 tools/integration_desktop_plugin.py --output /absolute/new/golem.mcpb`로 수행합니다. 생성은 설치·state 설정·승인·Work 실행을 하지 않습니다.
