# Legal Notice and Acceptable Use

NASO is a dual-use tool. The same capabilities that let a defender find their
own organisation's exposed credentials let someone else collect other people's.
Publishing it under an open source licence does not make every use of it lawful.

Read this before you deploy NASO, and read it again before you point it at
anything you do not own.

---

## 1. Intended use

NASO is built for **defensive and authorised** work:

- monitoring your own organisation's exposure in breach corpora;
- incident response and forensic investigation on systems you operate;
- red team and penetration testing engagements with written authorisation from
  the system owner;
- academic and security research conducted under an appropriate ethics and
  legal framework;
- threat intelligence work by a CERT/CSIRT or equivalent within its mandate.

## 2. Authorisation is your responsibility

You are solely responsible for ensuring that every collection, scan, query, and
correlation you perform with NASO is lawful in your jurisdiction and in the
jurisdiction of the target.

In particular, note that in most jurisdictions it is a criminal offence to:

- access a computer system without authorisation, including via credentials
  found in a breach corpus — **finding a password does not entitle you to use
  it**;
- port scan, probe, or enumerate infrastructure you do not own or have not been
  authorised in writing to test;
- intercept communications you are not a party to;
- possess or distribute certain categories of unlawfully obtained data.

Authorisation must be **specific, written, and current**. A prior engagement, a
public bug bounty policy you have not read, or an assumption that a target
"won't mind" is not authorisation.

## 3. Prohibited uses

You may not use NASO to:

- stalk, harass, dox, or surveil an individual;
- target journalists, activists, dissidents, or minority groups;
- collect, enrich, or resell personal data for advertising, credit scoring,
  insurance pricing, employment screening, or any other profiling of
  individuals without a lawful basis and their knowledge;
- gain unauthorised access to any system or account;
- facilitate extortion, fraud, credential stuffing, or the resale of breach
  data;
- circumvent a technical protection measure on a system you do not own.

These restrictions describe the use the authors intend and disclaim. They are
**not** additional terms on top of the GNU AGPL-3.0 licence and do not restrict
the freedoms that licence grants you. They are a statement of intent, and a
warning that the licence does not shield you from criminal or civil liability.

## 4. Data protection (GDPR and equivalents)

Breach corpora, dark web scrapes, and identity correlation graphs consist almost
entirely of **personal data** as defined by the EU GDPR (Regulation 2016/679),
the UK GDPR, and comparable regimes elsewhere.

If you deploy NASO and process such data, **you are the data controller**. The
authors of NASO are not. Specifically:

- **Lawful basis.** You must identify and document a lawful basis under Art. 6
  before processing. For most defensive security work this will be legitimate
  interests (Art. 6(1)(f)), which requires a documented balancing test — not an
  assumption.
- **Special categories.** Breach dumps routinely contain data revealing health,
  sexual orientation, political opinions, religious beliefs, or trade union
  membership, and sometimes criminal offence data. Art. 9 and Art. 10 impose
  substantially higher bars. Ingesting a corpus you have not triaged means you
  are almost certainly processing Art. 9 data.
- **DPIA.** Large-scale processing of personal data from breach sources,
  combined with the automated correlation and profiling NASO performs, will in
  most cases require a Data Protection Impact Assessment under Art. 35.
- **Data subject rights.** Individuals whose data you hold retain their rights
  of access, rectification, erasure, and objection (Art. 15–22). NASO does not
  implement these workflows for you. You must be able to answer such a request.
- **Retention and minimisation.** Do not retain a full corpus because it is
  convenient. Define retention periods and enforce them.
- **Transfers.** Be aware of where your storage and any LLM inference actually
  run. NASO supports fully local inference precisely so that payloads need not
  leave your infrastructure — if you point `AI_ENDPOINT` at a hosted API
  instead, you are exporting personal data to that provider.
- **Security of processing.** Art. 32 applies to your deployment, not to the
  upstream repository. See the operator responsibilities in
  [SECURITY.md](SECURITY.md).

Nothing in this document is legal advice. If you process breach data at scale,
consult a qualified data protection lawyer in your jurisdiction.

## 5. Third-party services and terms

NASO can query external services including Tor hidden services, Ahmia, Shodan,
and Telegram. Each has its own terms of service, rate limits, and acceptable use
policy, and some jurisdictions regulate the use of anonymity networks. Your use
of those services through NASO is governed by their terms and by local law, not
by this project. Bring your own credentials and respect their limits.

## 6. Export control and sanctions

Security and forensic tooling is subject to export control in some
jurisdictions, and to sanctions regimes that restrict who you may provide it to.
You are responsible for compliance with any such rules that apply to you.

## 7. No warranty and no liability

NASO is provided **as is**, without warranty of any kind, as set out in
sections 15 and 16 of the [GNU AGPL-3.0](LICENSE).

The authors and contributors accept no liability for any use of this software,
including any unlawful use, any data protection breach arising from a
deployment, any damage caused by a false positive or a missed detection, or any
consequence of acting on its output. Results are indicative and require human
verification before they are relied upon — particularly identity correlation and
AI-generated analysis, which are probabilistic and can be wrong.

## 8. Reporting misuse

If you believe NASO is being used against you or in breach of this notice,
contact <fabrizio.salmi@gmail.com>. Please note that the authors have no
visibility into and no control over third-party deployments: NASO is
self-hosted, and there is no central service to disable.

---

*Last reviewed: 2026-08. Licensed under the [GNU AGPL-3.0](LICENSE).*
