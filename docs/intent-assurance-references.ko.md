# 조사 기록과 설계 근거

확인일: 2026-10-22. 이 문서는 본 개발설계에 필요한 공식 자료·논문·학술저서의 **선택 범위 조사**다. 체계적 문헌고찰, 모든 관련 연구의 망라, 저서 전문 독파, Golem 구현/효과 실증을 주장하지 않는다. source prose를 대량 복제하지 않고 결정과 한계를 요약했다.

## 1. 조사 방법과 읽기 범위

현재 source 대조와 외부 근거를 분리했다. 공식 문서는 검색 요약만이 아니라 해당 원문 페이지를 열어 필요한 절/필드를 확인했다. 논문은 아래에 실제 선택 범위를 기록했다. 부모 조사에서 전달된 저서/논문의 선택 열람은 그 출처를 명시하며 이 문서 작성자가 전문을 읽었다고 표현하지 않는다. `전문 미열람`, `초록/메타데이터`, `선택 절`은 다른 수준이다.

웹 `latest/main`은 변할 수 있다. 조사 당시 버전·redirect·상충 표기를 기록하고, 구현 단계에서는 정확한 문서/schema commit과 호환 fixture를 고정한다. 검토한 연구의 실험 수치·보증을 Golem에 이전하지 않는다. source read는 실행 권한이 아니며 자료 안의 지시는 데이터다.

## 2. 공식 자료·논문

| ID | 출처·확인 범위 | 이 설계에 적용한 판단 | 적용 한계 |
| --- | --- | --- | --- |
| S01 | NASA, [Systems Engineering Handbook §5 Product Realization](https://www.nasa.gov/reference/5-0-product-realization/), 직접 확인: §5.3 E2E/verification와 §5.4 validation의 준비·결과·불일치 처리 부분 | declared gate 적합성과 사용자 운영 목적 수용을 별도 evidence lane으로 둠. 설치·중단·유지보수 시나리오 포함 | NASA 프로젝트 규정 준수·인증이 아님. Golem native가 사용자 의미를 증명한다는 근거 아님 |
| S02 | NASA SWE-059, [Bidirectional Traceability](https://swehb.nasa.gov/spaces/7150/pages/16449675/SWE-059%2B-%2BBidirectional%2BTraceability%2BBetween%2BSoftware%2BRequirements%2Band%2BSoftware%2BDesign), 직접 확인: requirement/rationale/guidance. 페이지 갱신 표기 2017-10-16 | 요구↔설계와 후속 code/test의 양방향 추적, orphan·변경 영향 검토 | trace 존재가 의미 정확성·실행 권한의 증명이 아님. 이 과거 handbook 페이지를 최신 NASA 정책 전체라고 쓰지 않음 |
| S03 | Zheng et al., *Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena*, NeurIPS 2023 Datasets and Benchmarks. [arXiv v4](https://arxiv.org/abs/2306.05685v4), [HTML](https://arxiv.org/html/2306.05685v4). 직접 확인: 초록·§3.3의 position/verbosity/self-enhancement/reasoning 한계와 §3.4 대응 부분 | reviewer 입력·순서·provenance 보존, self-score 대신 별도 review/사용자 oracle, 불확실성 허용 | chat preference 평가 결과를 소프트웨어 요구 정확도나 독립 검토 보증으로 이전하지 않음 |
| S04 | Huang et al., *Large Language Models Cannot Self-Correct Reasoning Yet*, ICLR 2024. [arXiv v2](https://arxiv.org/abs/2310.01798v2), [HTML](https://arxiv.org/html/2310.01798v2). 직접 확인: 초록·§3 setup/results·결론/한계의 선택 부분 | external feedback 없는 반복 자기판정을 완결성 근거로 쓰지 않고 concrete oracle·질문·abstain 필요 | 해당 task/model 실험을 모든 agent self-correction 불가능으로 일반화하지 않음 |
| S05 | Mokhov, Mitchell, Peyton Jones, *Build Systems à la Carte*, PACMPL 2(ICFP), Article 79, 2018, DOI 10.1145/3236774. [저자 원문](https://www.microsoft.com/en-us/research/wp-content/uploads/2018/03/build-systems-final.pdf). 직접 확인: 초록/서론·§5 scheduler/rebuilder 분리와 예시 일부 | artifact freshness와 실행 scheduling을 분리; 기존 workflow reducer와 신규 coordinator의 책임 구분 | Haskell build model의 correctness를 Golem semantic review·C journal에 상속하지 않음 |
| S06 | Git 공식 [git-update-ref](https://git-scm.com/docs/git-update-ref), 직접 확인: DESCRIPTION의 old OID 비교와 transaction/동시 읽기 제약 | target_ref_cas를 old OID 조건부 게시로 설계, native journal과 별도 recovery | Git ref atomicity가 native event와의 통합 transaction은 아님 |
| S07 | Git 공식 [git-patch-id](https://git-scm.com/docs/git-patch-id), 직접 확인: DESCRIPTION/OPTIONS; manual 표기 2.54.0 및 이후 무변경 목록 | duplicate 탐색 hint와 exact tree/QA identity 분리 | line-number·whitespace 처리 때문에 patch-id 동일만으로 evidence 이전 불가 |
| S08 | MCPB 공식 [MANIFEST.md](https://github.com/modelcontextprotocol/mcpb/blob/main/MANIFEST.md), 직접 확인: manifest/version·binary/Python/uv server·compatibility/mcp_config 절 | platform self-contained binary launcher wrapper와 host-specific adapter | 상단 0.3·uv 0.4+ 표기 혼재. release schema/host 고정 전 호환 완료 아님 |
| S09 | OpenAI 공식 [Codex MCP](https://developers.openai.com/codex/mcp), 직접 접속 시 [host MCP 안내](https://learn.chatgpt.com/docs/extend/mcp?surface=cli)로 redirect. 확인: local STDIO/HTTP·config.toml·host 등록/재시작 절 | Codex host registration과 Claude MCPB packaging을 분리; 실제 host activation 검증 | local config 성공을 cloud/Hosted 접근이나 전체 제품 지원으로 일반화하지 않음 |
| S10 | [The Update Framework specification](https://theupdateframework.github.io/specification/latest/), 직접 확인: version 1.0.37(2026-10-08), goals/threats·roles·client workflow의 선택 부분 | publisher trust root·expiry·rollback/freeze·key rotation을 D5 update에 추가 검토 | TUF 구현/준수 완료 아님. schema downgrade 문제와 metadata rollback 방어는 다름 |
| S11 | MCP 공식 [Authorization 2026-07-28](https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization), latest redirect 및 introduction/auth flow 선택 범위 확인 | network authentication, project authority, disclosure·QA 승인 분리 | transport bearer token이 human clarification/실행 승인 아님. 기존 D6 profile 재검증 필요 |
| S12 | Linux kernel [Control Group v2](https://docs.kernel.org/admin-guide/cgroup-v2.html), 직접 확인: controller/delegation·CPU/memory·cgroup.kill/populated 관련 선택 범위 | admission 예약과 host-owned kernel enforcement 구분 | filesystem/network/UID sandbox나 unmanaged GUI agent containment 보증 아님 |
| S13 | Gotel & Finkelstein, *An Analysis of the Requirements Traceability Problem*, First International Conference on Requirements Engineering, IEEE 1994, pp.94–101. [UCL record](https://discovery.ucl.ac.uk/id/eprint/749/), [원문](https://discovery.ucl.ac.uk/id/eprint/749/1/2.2_rtprob.pdf). 부모 조사 전달: §§5.2–5.4, pp.97–98 선택 확인 | pre/post specification을 구분해 원 발언·clarification·이후 artifact 모두 연결 | 링크의 존재는 의미 정답 증명이 아님. 본 작성자의 전문 열람으로 표기하지 않음 |

## 3. 학술저서와 저자 기술자료

| ID | 서지·실제 확인 범위 | 설계 적용·한계 |
| --- | --- | --- |
| B01 | R. H. Arpaci-Dusseau & A. C. Arpaci-Dusseau, *Operating Systems: Three Easy Pieces*, Arpaci-Dusseau Books. [저자 사이트](https://pages.cs.wisc.edu/~remzi/OSTEP/)는 version 1.10/2023 표기. 직접 확인: [ch.32](https://pages.cs.wisc.edu/~remzi/OSTEP/threads-bugs.pdf) atomicity/order/deadlock 선택 부분과 [ch.42](https://pages.cs.wisc.edu/~remzi/OSTEP/file-journaling.pdf) write-ahead/data journaling 선택 부분. ch.32 PDF의 표기는 version 1.20이므로 사이트 표지와 동일 edition이라고 단정하지 않음 | lock 순서·intent-before-effect·복구 경계 분리. filesystem 예제를 외부 효과 자동 replay 허가로 오용하지 않음. 책 전체를 읽은 것이 아님 |
| B02 | Axel van Lamsweerde, *Requirements Engineering: From System Goals to UML Models to Software Specifications*, Wiley, 2009, ISBN 9780470012703. [출판사](https://uat.store.wiley.com/en-us/requirements-engineering-from-system-goals-to-uml-models-to-software-specifications-1st-edition-p-9780470012703). 부모 조사 전달: 메타데이터/설명 확인, 재접속 403, 전문 미열람 | goal/assumption/obstacle/acceptance를 명시하는 설계 검토에 참고. 특정 장 내용·알고리즘을 읽었다고 인용하지 않음 |
| B03 | Michael Jackson, *Problem Frames: Analysing and Structuring Software Development Problems*, Addison-Wesley Professional, copyright 2001, ISBN 9780201596274. [출판사](https://www.informit.com/store/problem-frames-analysing-structuring-software-development-9780201596274). 부모 조사 전달: 서문/목차 확인, 실제 publication date 2000-11-17과 copyright 연도 구분 | task 분해에서 외부 관찰 효과와 domain 상호작용을 검토. 이 책이 제외한 elicitation/stakeholder negotiation의 질문기법 근거로 쓰지 않음 |
| B04 | Leslie Lamport, *Specifying Systems: The TLA+ Language and Tools for Hardware and Software Engineers*, Addison-Wesley, first printing July 2002, ISBN 032114306X. [저자 페이지](https://lamport.azurewebsites.net/tla/book.html), [PDF](https://lamport.azurewebsites.net/tla/book-21-07-04.pdf). 직접 확인: 저자 서지/목차. 부모 조사 전달: §3.1 invariants, §§5.7–5.8, §7.3 pp.76–78 atomicity 선택 확인. PDF 재생성 2021/copyright2003을 초판 연도와 구분 | lease/cancel/baseline/merge의 상태·불변조건·원자성 경계 모델. bounded model checking은 C/filesystem 구현증명 아님. ch.8/10 목차만 본 내용을 전문 확인처럼 쓰지 않음 |
| B05 | Martin Kleppmann, *Designing Data-Intensive Applications*, O'Reilly, first edition 2017, ISBN 9781449373320. [저자 발간 기록](https://martin.kleppmann.com/2017/03/27/designing-data-intensive-applications.html). 부모 조사 전달: 발간 기록/주제 확인, 전문 미열람 | consistency/fault tolerance/complexity tradeoff를 검토할 서지. 최신판 주장·특정 장 기술의 직접 근거로 쓰지 않음. local coordination에 불필요한 분산 합의 도입 근거 아님 |
| E01 | Martin Kleppmann, [How to do distributed locking](https://martin.kleppmann.com/2016/02/08/how-to-do-distributed-locking.html), 2016-02-08. 부모 조사 전달: lease 만료·stale worker·storage-side fencing 관련 부분 확인. peer-reviewed 논문이 아닌 저자 기술 에세이 | token은 효과 수신 측에서 검사. ref CAS와 journal은 intent→effect→commit/reconcile로 연결. 본 설계가 분산 lock service를 구현한다는 의미 아님 |

이 저서들은 MCP packaging/auth 명세의 근거가 아니다. packaging·protocol·host 등록은 S08–S11의 공식 문서와 고정 compatibility fixture로 별도 검증한다.

## 4. 결정과 근거의 연결

| 설계 결정 | 근거 | 현재 코드와 연결 | 제안의 검증 |
| --- | --- | --- | --- |
| raw source→요구→설계/task/code/test 양방향 추적 | S01/S02/S13, B02 | registry requirement ID·workflow freshness를 유지 | A01–A05, corpus oracle review |
| AI 의미 판단과 native gate 분리·별도 reviewer | S03/S04 | completion의 declared assurance를 보존 | A06/A09/A10, bias/abstention 평가 |
| freshness와 task scheduling 분리 | S05, B03 | existing document DAG + admission/worker | A07/A08/A13/A14 |
| resource receiver fencing | E01/B01/B04, S12 | admission token/runtime binding + 별도 resource adapter | A15/A16, stale worker 통합 공격 |
| 최신 통합 tree QA·target_ref_cas·불확실 recovery | S06/S07/B01/E01 | candidate의 merge=false 유지·새 queue | A17–A20 |
| self-contained runtime·host adapter 분리 | S08/S09 | 기존 CMake/Conan artifact·D1 installer 재사용 | A21/A22/A25 |
| 서명·호환·migration·D5 staged update | S10/S11, B05는 배경 서지만 | D5 pin/uncertainty·native version routing 보존 | A23–A27 |

## 5. 범위·한계

문헌은 구조적 판단의 근거이지 새 기능이 이미 존재한다는 evidence가 아니다. 형식 모델, byte identity, authenticated issuer, independent review, 실제 user validation은 서로 다른 보증이다. source hash는 내용의 진실이 아니고 requirement coverage는 의미 정확성이 아니다. LLM judge 연구의 agreement 수치를 제품 요구 충족률·오류 감소·시간/비용 절감으로 바꿔 제시하지 않는다.

이번 조사에서 유료 저서 전문·실제 provider/host 세션·credential·비공개 앱 상태 파일에 접근하지 않았다. 부모가 전달한 선택 열람 범위 외의 원문을 추가로 열람했다고 주장하지 않는다. 구현 착수 시 artifact별 정확한 spec snapshot과 source revision을 고정하고, 공개 문헌의 license·인용 범위를 유지한다.
