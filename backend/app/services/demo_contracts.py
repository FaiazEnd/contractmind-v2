"""Benchmark demo contract corpus for instant studio loading & Deal Room multi-doc auditing."""

from __future__ import annotations

from typing import Dict

DEMO_CONTRACTS: Dict[str, Dict[str, str]] = {
    "msa": {
        "title": "Apex Cloud Enterprise Master Services Agreement (MSA)",
        "filename": "apex_enterprise_msa_v4.pdf",
        "playbook": "Standard Corporate Playbook",
        "text": """Section 1. Scope of Enterprise Services
Provider (Apex Cloud Systems Inc.) shall deliver the enterprise cloud platform and dedicated deployment services in accordance with the Service Level Agreement (99.95% monthly uptime). If monthly uptime falls below 99.95%, Provider shall issue Service Credits of 15% of monthly fees within 30 days following a verified SLA shortfall claim.

Section 2. Fees and Payment Terms
Customer shall pay all undisputed subscription invoices Net 30 days from invoice receipt via ACH or corporate wire. Overdue balances may accrue 1.5% monthly interest after 10 days' written notice.

Section 3. Uncapped Indemnification
Customer shall indemnify and hold harmless Provider, its affiliates, and its officers from and against any and all claims whatsoever, without limitation or cap on liability, arising out of Customer's use of the platform or third-party integrations, including Provider's own negligence.

Section 4. Limitation of Liability & Damages
Except for payment obligations, Provider's aggregate cumulative liability under this Agreement shall not exceed $50,000, and Customer remains liable for all indirect, consequential, incidental, special, and lost profits damages suffered by Provider.

Section 5. AI Model Training & Customer Data License
Customer hereby grants Provider a perpetual, royalty-free, irrevocable license to ingest Customer Data, prompts, and telemetry to train its AI and machine learning models and improve its artificial intelligence algorithms across commercial offerings.

Section 6. Term, Auto-Renewal & Termination
This Agreement shall have an Initial Term of three (3) years and shall automatically renew for successive 3-year terms unless Customer delivers written non-renewal notice at least 120 days prior to expiration. Provider may terminate immediately without prior notice or cure period at Provider's sole discretion upon any suspected policy deviation. Upon termination, Customer shall pay an early termination fee equal to 100% of remaining term fees as liquidated damages.

Section 7. Security Audits, Insurance & Data Deletion
Provider maintains SOC 2 Type II certification and cyber liability insurance ($5,000,000 coverage), delivering certificates within 15 days of annual renewal. Customer grants Provider unlimited audit rights to audit Customer systems at any time without notice at Customer's sole expense. Upon termination, Provider shall return and delete all Customer Data within 30 days.

Section 8. Governing Law, Precedence & Legal Fees
This Agreement is governed by the laws of the State of Delaware. In any dispute, Customer shall reimburse Provider's attorneys' fees and collection costs unconditionally. In the event of a conflict, this Master Agreement controls unless a Schedule expressly prevails.
""",
    },
    "cloud_dpa": {
        "title": "Apex Global Data Processing Addendum (DPA)",
        "filename": "apex_global_cloud_dpa.pdf",
        "playbook": "Strict Privacy & AI Governance Playbook",
        "text": """Section 1. Purpose and Order of Precedence
This Data Processing Addendum supplements the Master Services Agreement. Notwithstanding anything to the contrary, the terms of this DPA shall prevail over the Master Agreement with respect to all liability, data ownership, and commercial remedies.

Section 2. Subprocessor Engagement & Liability Shield
Processor may engage third-party subprocessors without prior notice or Customer consent, and Processor expressly disclaims all liability for third-party subprocessors and transfers Customer Data globally without consent.

Section 3. Limitation of Liability & AI Processing
Processor's aggregate liability under this DPA shall be uncapped and unlimited for regulatory fines, while Processor retains the right to train machine learning models on aggregated Customer Data prompts.

Section 4. Security Incident Notice & Audit Rights
Processor shall provide written notice within 72 hours of confirming a Personal Data Breach. Processor undergoes annual ISO 27001 and SOC 2 Type II security audits and provides summary reports within 30 days of written request.

Section 5. Data Deletion Upon Termination
Processor shall cryptographically delete or return all Customer Personal Data within 30 days of termination, except archival backups retained indefinitely unless separately purged.

Section 6. Governing Law
This DPA shall be governed by the laws of the State of New York, and any dispute shall be resolved exclusively in Manhattan courts.
""",
    },
    "saas": {
        "title": "HorizonAI SaaS Order Form & Enterprise Subscription",
        "filename": "horizonai_saas_order_form.pdf",
        "playbook": "Standard Corporate Playbook",
        "text": """Section 1. Subscription Services & SLA
HorizonAI grants Customer access to the Enterprise Copilot Workspace with 99.9% uptime SLA and monthly service credits upon written claim within 30 days.

Section 2. Pricing, Exclusivity & Non-Compete
Customer agrees to pay $240,000 annually Net 30 days. During the Term and for two (2) years thereafter, Customer shall designate HorizonAI as its exclusive provider and shall not engage, procure, or develop any competing AI workflow software or services worldwide.

Section 3. Liability Cap & Consequential Damages
Aggregate liability under this Order Form shall not exceed 12 months of fees paid. Neither party excludes liability for consequential or indirect damages arising from early cancellation, and Customer shall pay liquidated damages equal to 100% of remaining term fees upon termination.

Section 4. Termination & Auto-Renewal
This subscription shall automatically renew for successive 3-year terms without prior notice unless canceled 90 days before renewal. Vendor may terminate immediately without opportunity to cure for any non-payment beyond 5 days.

Section 5. Governing Law
This Order Form is governed by the laws of the State of California.
""",
    },
    "ma": {
        "title": "NovaTech Strategic M&A Asset Purchase Agreement",
        "filename": "novatech_asset_purchase_agreement.pdf",
        "playbook": "Standard Corporate Playbook",
        "text": """Section 1. Purchase Price & Escrow Payment
Buyer shall remit $48,000,000 at Closing plus $6,000,000 into Escrow payable within 15 business days of Closing certification.

Section 2. Seller Indemnification & Liability Exposure
Seller shall indemnify and hold harmless Buyer from any and all claims whatsoever without limitation or uncapped indemnification for pre-closing tax, IP, and environmental liabilities, and Seller remains liable for all indirect, consequential, and lost profits damages.

Section 3. Non-Compete Covenant
For a period of seven (7) years worldwide, Seller and its affiliates shall not develop, market, or invest in any competing enterprise software products, constituting a worldwide non-compete restriction.

Section 4. Post-Closing Audit & Fee Shifting
Buyer may conduct unannounced on-site audits of Seller's transition records at any time without notice at Seller's sole expense. In any post-closing arbitration, Seller shall reimburse Buyer's attorneys' fees unconditionally.

Section 5. Data Transition & Termination
Seller shall delete all transferred customer records within 30 days after transition completion and provide written notice of completion. Either party may terminate pre-closing immediately without cure period upon any perceived regulatory inquiry.

Section 6. Governing Law
This Agreement is governed by the laws of the State of Delaware.
""",
    },
    "joint_ip": {
        "title": "QuantumBio Joint IP Development & Licensing Agreement",
        "filename": "quantumbio_joint_ip_agreement.pdf",
        "playbook": "Standard Corporate Playbook",
        "text": """Section 1. Joint Research Scope & Milestones
Parties shall collaborate on therapeutic discovery algorithms with quarterly milestone reviews and Net 45 payment schedules.

Section 2. AI Model Training & Background IP
Licensor may train its AI and foundation models on Partner's proprietary assay datasets and retain a perpetual license to Customer Data derived from joint experiments.

Section 3. Exclusivity & Non-Compete
Partner appoints Licensor as exclusive provider of computational biology pipelines and shall not procure or develop competing services globally for 5 years.

Section 4. Indemnification & Consequential Damages
Partner shall indemnify Licensor without limitation for downstream clinical claims, and no consequential damages waiver applies to royalty shortfalls.

Section 5. Audit Rights & Termination
Licensor may audit Partner laboratories at any time without notice and may terminate immediately without notice or cure upon milestone delay.

Section 6. Governing Law
Governed by the laws of England and Wales.
""",
    },
    "nda": {
        "title": "Vertex Ventures Mutual Non-Disclosure Agreement (NDA)",
        "filename": "vertex_mutual_nda.pdf",
        "playbook": "Standard Corporate Playbook",
        "text": """Section 1. Definition of Confidential Information
Confidential Information includes all technical, financial, product roadmap, and customer disclosures marked confidential or reasonably understood to be proprietary.

Section 2. Permitted Use & AI Restriction
Recipient shall use Confidential Information solely to evaluate the Proposed Transaction and shall NOT use Discloser's materials to train machine learning or AI models, except aggregated insights from customer data may be retained internally unless prohibited.

Section 3. Return or Destruction & Notice
Within 15 days of written request, Recipient shall destroy or return all Confidential Information and certify deletion in writing. Any unauthorized disclosure requires written notice within 24 hours.

Section 4. Remedies & Fee Shifting
In any enforcement action, Recipient shall reimburse Discloser's unilateral legal fees and collection costs, and Discloser may seek injunctive relief plus liquidated damages penalty of $500,000 per breach.

Section 5. Governing Law
This NDA is governed by the laws of the State of Delaware.
""",
    },
}
