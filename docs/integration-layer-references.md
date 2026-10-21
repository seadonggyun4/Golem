# Integration Layer: Research and Decision Record

검토일: 2026-10-21. 대상: [통합 설계](integration-layer-design.md).
공식 명세·논문·학술/기술서의 아래 선택된 절·초록을 열람했다. 책 전체 정독,
선행 시스템 전수 재현, Golem 효과 실험, 규격 준수를 주장하지 않는다.
출처의 주장과 Golem에 적용한 설계 추론을 구분한다. 외부 자료는 설치·실행 지침이 아니다.

## Standards and Client Contracts

### S1. MCP Versioning

Model Context Protocol, revision `2026-07-28`, [Versioning and Compatibility](https://modelcontextprotocol.io/specification/2026-07-28/basic/versioning).
열람: modern/legacy 구분, request metadata, unsupported version, backward compatibility.
modern의 요청별 버전과 legacy 초기화 방식은 다르다. 적용: transport profile을 나누고
native/session/domain identity를 분리한다. 한계: 명세 지원과 실제 SDK/client 지원은 별개다.

### S2. MCP Transports

MCP `2026-07-28`, [stdio](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/stdio),
[Streamable HTTP](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http).
열람: framing/stdout, modern HTTP 변경, Origin/localhost/authentication, backward compatibility.
적용: local stdio 기본, HTTP 별도 보안 모드, protocol JSON 외 stdout 금지.
한계: localhost나 stdio 자체가 사람 신원 인증·sandbox를 제공하지 않는다.

### S3. MCP Roots

MCP `2026-07-28`, [Roots](https://modelcontextprotocol.io/specification/2026-07-28/client/roots).
열람: deprecated 안내와 접근 제어 한계. 적용: 새 grant를 roots 위에 세우지 않는다.
legacy roots는 발견 hint다. 한계: roots 목록의 존재는 디스크 접근·사용자 승인이 아니다.

### S4. MCP Tools and Resources

MCP `2026-07-28`, [Tools](https://modelcontextprotocol.io/specification/2026-07-28/server/tools),
[Resources](https://modelcontextprotocol.io/specification/2026-07-28/server/resources).
열람: user interaction, schemas, annotations, 목록 결정 규칙, resource의 host-driven 사용.
적용: focused typed tools, 요청별 auth subset, scoped resource, 원문 수신과 단순 노출 구분.
한계: annotation·resource 제공은 실제 권한 집행·모델 로딩의 증명이 아니다.

### S5. OpenAI Client Contract

OpenAI, [Model Context Protocol](https://developers.openai.com/codex/mcp), live official documentation.
열람: supported features, local/shared/project configuration, client surfaces.
적용: host별 설정 adapter, trusted-project scope, stdio/HTTP 분리.
한계: 설정 공유가 모든 Hosted 입력·hook·전체 대화 접근을 뜻하지 않는다.
정확한 host/client 버전의 probe로 지원을 확정한다. 이 설계에서 실제 client 설치는 하지 않았다.

### S6. Claude Code Contract

Anthropic, [MCP](https://code.claude.com/docs/en/mcp), [Hooks reference](https://code.claude.com/docs/en/hooks).
열람: project/local/user scope와 precedence, noninteractive 승인 차이, SessionStart/compact.
적용: 관리 항목만 patch하고 hook은 readonly attach로 제한한다.
한계: Code 동작을 Desktop/웹에 일반화하지 않는다. hook 자체는 고권한 실행 경로다.

### S7. Authorization and Provenance

MCP, [Authorization](https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization),
[Security Best Practices](https://modelcontextprotocol.io/docs/2026-07-28/tutorials/security/security_best_practices).
열람: HTTP OAuth 역할, audience, confused deputy, token passthrough, local compromise, proxy.
적용: 원격 인증과 Work 권한을 분리하고 local delegate에 원래 주체를 보존한다.
한계: MCP 인증만으로 native owner/sequence를 대체할 수 없다.

Lodderstedt, Bradley, Labunets, Fett, [RFC 9700: Best Current Practice for OAuth 2.0 Security](https://www.rfc-editor.org/rfc/rfc9700), 2025.
열람: security recommendations와 access-token privilege restriction 관련 부분.
적용: issuer/audience·scope 제한과 credential 재사용/전달 방지. 구현 준수는 향후 별도 검증한다.

W3C, [PROV-DM](https://www.w3.org/TR/prov-dm/), Recommendation, 2013.
열람: entity/activity/agent·derivation·responsibility 개념.
적용: 실행 사실·판단·전달·검토·인증 출처 분리. 제안 JSON은 PROV 표준 직렬화가 아니다.

## Papers

### S8. Protection Principles

Jerome H. Saltzer, Michael D. Schroeder, *The Protection of Information in Computer Systems*,
Proceedings of the IEEE 63(9), 1975, pp. 1278-1308.
[저자 보관본](https://web.mit.edu/Saltzer/www/publications/protection/),
[Basic Principles](https://web.mit.edu/Saltzer/www/publications/protection/Basic.html).
열람: 인증/권한 정의와 fail-safe defaults, complete mediation, least privilege.
적용: project/client/destination별 grant와 매 요청 검사, 모델의 권한 자기발급 금지.
한계: 같은 OS 계정의 악성 writer까지 로컬 JSON으로 격리할 수 있다는 결론은 아니다.

### S9. End-to-End Placement

J. H. Saltzer, D. P. Reed, D. D. Clark, *End-to-End Arguments in System Design*,
ACM Transactions on Computer Systems 2(4), 1984, pp. 277-288.
[저자 보관 논문](https://web.mit.edu/Saltzer/www/publications/endtoend/endtoend.pdf).
열람: 서론, reliable file transfer와 설계 논증.
적용: transport 성공/adapter preflight는 최종 native fence를 대체하지 않는다.
한계: 논문이 Golem의 정확성이나 이 계층 배치를 검증한 것은 아니다.

### S10. Ordering and Clocks

Leslie Lamport, *Time, Clocks, and the Ordering of Events in a Distributed System*,
Communications of the ACM 21(7), 1978, pp. 558-565.
[저자 설명·서지](https://www.microsoft.com/en-us/research/publication/time-clocks-ordering-events-distributed-system/).
열람: 저자의 인과/부분순서·state-machine 설명. 별도 원문 PDF 주소는 timeout으로 열람 실패.
적용: event sequence/digest와 causality를 wall time과 구분하고 두 stream의 전역 순서를 추측하지 않는다.
한계: Lamport clock/consensus를 새로 구현하거나 native monotonic lease를 대체하지 않는다.

### S11. Coordination and Modular Boundaries

Mike Burrows, *The Chubby Lock Service for Loosely-Coupled Distributed Systems*, OSDI, 2006.
[저자 소속 연구기관 페이지](https://research.google/pubs/the-chubby-lock-service-for-loosely-coupled-distributed-systems/).
열람: 초록·서비스 범위. PDF fetch는 redirect 제한으로 실패했다.
적용: 조정 lock의 역할을 실행 효과/신원과 구분. 구체적 fencing은 기존
[native session](agent-session.md) 계약을 직접 재사용한다.
한계: 초록만으로 sequencer 알고리즘이나 Golem과의 동등성을 입증하지 않는다.

David L. Parnas, *On the Criteria To Be Used in Decomposing Systems into Modules*,
CACM 15(12), 1972, pp. 1053-1058, DOI 10.1145/361598.361623.
[대학의 논문 전사본](https://www.cs.lafayette.edu/~gexia/cs301/resources/parnas.html).
열람: modularization 기준·changeable decisions의 은닉.
적용: client 설정/MCP wire/native backend를 변화 이유에 따라 분리한다.
한계: publisher PDF 대신 정확성을 보증하지 않는 전사본을 열람했고 성능 증거로 쓰지 않는다.

### S12. Supply-Chain Evidence

Santiago Torres-Arias, Hammad Afzali, Trishank Karthik Kuppusamy, Reza Curtmola, Justin Cappos,
*in-toto: Providing Farm-to-Table Guarantees for Bits and Bytes*, USENIX Security 2019, pp. 1393-1410.
[학회 페이지·초록·서지](https://www.usenix.org/conference/usenixsecurity19/presentation/torres-arias).
열람: 초록과 단계별 공급망 위협 설명.
적용: binary hash와 승인 producer/build/SDK/검증 단계의 근거를 구분한다.
한계: Golem installer의 in-toto 준수나 서명된 출처가 이미 있다는 주장이 아니다.

### S13. Indirect Prompt Injection

Qiusi Zhan, Zhixiang Liang, Zifan Ying, Daniel Kang,
*InjecAgent: Benchmarking Indirect Prompt Injections in Tool-Integrated Large Language Model Agents*,
Findings of ACL 2024, [저자 preprint v3](https://arxiv.org/abs/2403.02691v3).
열람: abstract·버전/출판 정보. 외부 도구 내용에 들어간 지시가 agent 동작을 오염시킬 수 있다.
적용: quoted evidence와 authority를 분리하고 권한·실행을 기계적 계약으로 강제한다.
한계: injection 제거 보장이나 논문의 수치가 Golem에도 적용된다는 뜻이 아니다.

## Books and Update Framework

### S14. Engineering Books

Titus Winters, Tom Manshreck, Hyrum Wright (eds.), *Software Engineering at Google*, O'Reilly, 2020.
[Chapter 11: Testing Overview](https://abseil.io/resources/swe-book/html/ch11.html),
[Chapter 13: Test Doubles](https://abseil.io/resources/swe-book/html/ch13.html),
[Chapter 18: Build Systems and Build Philosophy](https://abseil.io/resources/swe-book/html/ch18.html).
열람: 자동 시험의 역할, test double과 real implementation의 trade-off, 빌드 입력/정확성 설명.
적용: mock/native/MCP/client 활성화를 별도 시험하고 정확한 입력 pin을 보존한다.
한계: 책 전체 정독이나 이 설계의 maintainability 측정 결과를 주장하지 않는다.

Scott Chacon, Ben Straub, *Pro Git*, 2nd edition, Apress, 2014,
[Chapter 10.2: Git Objects](https://git-scm.com/book/en/v2/Git-Internals-Git-Objects).
열람: object/commit/storage 설명.
적용: 내용 identity와 변경 이력을 구분하고 원래 evidence bytes를 다시 쓰지 않는다.
한계: Git object가 Golem CAS 형식과 같거나 publisher 인증이라는 뜻은 아니다.

Martin Kleppmann, *Designing Data-Intensive Applications*, O'Reilly, 2017,
[저자 책 소개](https://dataintensive.net/).
열람: 공개 소개의 reliability/scalability/maintainability와 설계 trade-off만.
적용: 원본과 재구성 가능한 읽기 cache를 구분한다.
한계: 출판사 본문 URL은 404였으므로 특정 장·transaction 보장을 인용하지 않는다.
구체적인 commit/retry 의미는 기존 Golem 계약과 시험으로 확정한다.

Maarten van Steen, Andrew S. Tanenbaum, *Distributed Systems*, 4th edition, 2023,
[저자 배포 페이지](https://www.distributed-systems.net/index.php/books/ds4/).
열람: 판본·디지털판 제공 정보만. 후속 읽기 목록이며 규칙의 직접 증거로 사용하지 않는다.

### S15. Secure Update Metadata

The Update Framework, [Specification](https://theupdateframework.github.io/specification/latest/),
열람 당시 version `1.0.37`, last modified 2026-10-08.
열람: goals/threats, client workflow, rollback/freeze checks와 metadata expiry.
적용: 무인 update에는 신뢰 root와 서명 version/expiry 검증이 필요하다.
한계: 수동 source-build 설치를 TUF 준수로 표시하지 않으며 새 key infrastructure도 만들지 않았다.

## Alternatives and Decisions

이전 공개 MCP 조사에서 아래 고정 소스를 비교했다. 제품 전체 동등성·전수 부재 판정은 아니다.
관측 기능을 참고할 뿐 외부 코드 복사나 installer 실행을 승인하지 않는다.

| 대안 | 고정 source | 교훈 / 채택하지 않는 것 |
| --- | --- | --- |
| Task Orchestrator | [5322daf](https://github.com/jpicklyk/task-orchestrator/tree/5322daf8b4d9dc1901113fd0e1d351d9fbba094f) | 서버 gate/claim/lease는 이미 존재. core를 새 task DB로 대체하지 않음 |
| FlowMCP | [daff589](https://github.com/PeterGreenAppliedAI/FlowMCP/tree/daff5897b77d8affd064f174c261d7cea7a07cc1) | 확인 checkpoint와 host 승인을 구분. 자체 Work authority로 수입하지 않음 |
| Beads | [f3c4739](https://github.com/gastownhall/beads/tree/f3c47390e7885c6cbfc0fd043b4a7a90d002755e) | client setup/context 연결 사례. project consent를 대신하지 않음 |
| MCP Agent Mail | [7aa20e2](https://github.com/Dicklesworthstone/mcp_agent_mail/tree/7aa20e2023161b785320bf8912dc5ee062e8c3da) | 메시지/예약/인계 가능. advisory 예약과 native fencing은 다름 |
| Marrow MCP | [868a9c1](https://github.com/getmarrow/marrow-mcp/tree/868a9c18530a75fcee5052441d0d3d2383511df4) | client 연결/runtime 거버넌스 분리. 원격 backend는 미검증 |

결정: core 유지, Python 기반 얇은 service와 pinned official MCP SDK를 검토하며 local stdio부터
시작한다. 단일 필수 daemon, client별 engine 복제, 별도 semantic memory DB, 자유 shell tool,
자동 대화 수집, roots 기반 승인, 모델/SDK의 무조건 최신 교체는 제외한다.
후속 구현에서 SDK/version·라이선스·dependency inventory·실제 client profile을 다시 검증한다.
