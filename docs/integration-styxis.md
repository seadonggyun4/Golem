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

The catalog pins the installation adapter, skills and Desktop archive. The selected local launcher separately identifies the native executable, MCP runtime and policy pins; a catalog update alone does not replace them. Verify both the public package and the selected local runtime before claiming an update is active.

카탈로그 패키지와 실제 선택된 native·MCP runtime은 별도로 대조합니다. 연결 후 새 Work를 시작할 때는 [관리형 bootstrap 안내](mcp-managed-bootstrap.ko.md)의 도구 진단과 Owner 초안 검토 경로를 따릅니다. 도구 노출·준비 성공은 실행 승인이 아닙니다.

## Setup and migration / 설정·전환

1. Verify the catalog's exact source SHA and package inventory. For Desktop, verify the linked archive SHA as well. Product code stays in Golem.
2. Review an owner-private JSON containing only the existing launcher's absolute `command` and string `args`. Preserve its runtime·native·producer·policy pins.
3. Configure the installed adapter with the exact reviewed JSON digest and the intended `--client`: `codex`, `claude-code`, `portable`, or `claude-desktop`. The Desktop state path must match its Configure selection. This records launcher selection, not native action approval.
4. Preserve recovery files and use official removal/update paths to leave one verified Golem connection per client. Existing private launcher-only packages must not silently import adapter state.
5. Confirm installation, handshake, tool definitions and authorized calls separately. Existing Work execution HOLD, approvals, Work, evidence and `COMMIT_UNKNOWN` remain in force. Expired observation contracts require separate renewal; a reinstall does not renew them.

기존 Golem 저장소 카탈로그는 신규 배포 항목 없는 호환 표식입니다. Owner 전용 private marketplace 생성기는 유지보수·격리 검증에만 사용합니다. Styxis 등록은 공개된 정확한 commit의 전체 plugin inventory를 검사한 뒤 진행하며 미게시 변경을 과거 SHA에 붙이지 않습니다.

공개 Desktop 패키지 생성은 `python3 tools/integration_desktop_plugin.py --output /absolute/new/golem.mcpb`로 수행합니다. 생성은 설치·state 설정·승인·Work 실행을 하지 않습니다.

## Updates / 갱신

Codex의 선택 state와 실제 활성 서비스가 다르면 Owner 앱의 **Codex 연결·갱신**에서
확인한다. [Golem 연결 갱신](integration-connection-renewal.md)은 이미 검토한 state만
선택하며, 최초 adapter 교체와 실제 모델 도구 전달 검증을 대신하지 않는다.

Update the public adapter through Styxis, then compare the resolved client command, selected state and running launcher. An absolute path to an older installed adapter must be updated through the client's supported configuration path; refreshing the catalog alone does not change that path.

Owner 앱은 별도 검토한 UI 파일·실행 경로를 사용합니다. UI만 갱신할 때는 해당 파일 inventory와 SHA를 대조하고, 기존 MCP runtime·native·정책·승인 state를 유지합니다. 앱의 연결 표시는 관측 결과이며 권한이나 최신 Work 상태를 인증하지 않습니다. Codex 갱신은 Claude 설치·state를 변경하는 동의가 아닙니다.
