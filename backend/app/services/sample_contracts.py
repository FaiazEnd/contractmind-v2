"""Six benchmark commercial contract templates for 1-click Demo & Deal Room audits."""
from __future__ import annotations

from typing import Any


SAMPLE_CONTRACTS: dict[str, dict[str, Any]] = {
    "ma": {
        "title": "TechNova Asset & IP Acquisition Agreement (M&A)",
        "category": "M&A & IP",
        "playbook_name": "Strict M&A & IP Playbook",
        "filename": "technova_ma_acquisition.pdf",
        "text": """ASSET AND INTELLECTUAL PROPERTY PURCHASE AGREEMENT

Section 1. Purchase Price and Escrow Payment Terms
Buyer shall remit the Purchase Price of USD 24,500,000 at Closing, with payment terms Net 30 days for working capital true-up adjustments.

Section 2. Uncapped Indemnification and Remedies
Seller shall indemnify, defend, and hold harmless Buyer and its affiliates from and against all claims whatsoever arising from pre-closing operations, intellectual property title, or third-party assertions, without limitation or monetary cap, regardless of any cap elsewhere in this Agreement. Consequential and indirect damages shall be recoverable in full and are not excluded.

Section 3. Non-Compete and Perpetual Exclusivity
For a period of ten (10) years following Closing, Seller and its founders agree to a perpetual worldwide non-compete prohibiting them from engaging in any software, technology, or enterprise business whatsoever.

Section 4. Asymmetric Attorney Fee Shifting
In any litigation or arbitration arising under this Agreement, only Seller shall reimburse Buyer for all outside attorneys' fees and legal costs regardless of which party prevails.

Section 5. Governing Law and Order of Precedence
This Agreement shall be governed by and construed in accordance with the laws of the State of Delaware. Upon termination or closing unwind, Seller shall delete or destroy all retained buyer diligence records within 30 days and deliver written certification.
""",
    },
    "cloud_dpa": {
        "title": "Enterprise Cloud Data Processing Addendum (DPA)",
        "category": "Cloud & SaaS",
        "playbook_name": "Cloud & GDPR Privacy Playbook",
        "filename": "enterprise_cloud_dpa.pdf",
        "text": """ENTERPRISE CLOUD DATA PROCESSING ADDENDUM (DPA)

Section 1. Scope and AI Model Training Rights
Processor processes Customer Personal Data to deliver hosted cloud services. Notwithstanding confidentiality obligations, Customer grants Processor a perpetual, royalty-free license to use Customer Data, prompts, and inputs to train our artificial intelligence and machine learning models.

Section 2. Subprocessor Engagement & Liability Shield
Processor may engage any third-party subprocessor without prior notice to Customer and may transfer personal data to any jurisdiction without safeguards. Processor shall have no liability for subprocessor breaches and is shielded from liability arising from third-party infrastructure providers.

Section 3. Security Audit Rights and Attestation
Customer may conduct an on-site security audit at any time without prior notice, with unlimited audit access at the sole expense of Customer. Processor maintains annual SOC 2 Type II certification and Cyber Liability insurance of USD 5,000,000.

Section 4. Data Deletion and Breach Notification
Upon expiration or termination, Processor shall provide written breach notification within 48 hours of any security incident and shall return or securely delete all Personal Data within 30 days of termination.

Section 5. Governing Law and Limitation of Liability
This Addendum is governed by the laws of the State of California. Consequential damages are excluded solely for Vendor, while Customer remains liable for indirect losses.
""",
    },
    "joint_ip": {
        "title": "Strategic Joint IP Development & Licensing Agreement",
        "category": "M&A & IP",
        "playbook_name": "Strict M&A & IP Playbook",
        "filename": "strategic_joint_ip_agreement.pdf",
        "text": """STRATEGIC JOINT INTELLECTUAL PROPERTY DEVELOPMENT AGREEMENT

Section 1. Co-Development Milestones & Payment Schedule
Partner shall remit milestone development fees Net 30 days from invoice receipt as detailed below:
| Milestone | Deliverable | Fee (USD) | Due Window |
| --- | --- | --- | --- |
| Phase 1 | Architecture & Core SDK | $250,000 | Net 30 days |
| Phase 2 | Production Model Weights | $400,000 | Net 30 days |

Section 2. AI Training and Derivative Model Ownership
Vendor receives an irrevocable, perpetual license to use Customer Data, proprietary prompts, and co-developed datasets to train artificial intelligence models for commercial resale.

Section 3. Exclusivity and Non-Compete Covenant
Customer agrees to worldwide exclusivity for five (5) years and is prohibited from engaging any other AI or software vendor in any technology domain whatsoever.

Section 4. Indemnification & Liquidated Damages
Customer shall indemnify Vendor without limitation for any third-party patent assertions. Any early termination triggers liquidated damages equal to 100% of remaining contract fees as an immediately accelerated punitive multiplier.

Section 5. Termination and Governing Law
Vendor may terminate immediately without notice or cure period for any perceived covenant breach. This Agreement is governed by the laws of the State of New York.
""",
    },
    "msa": {
        "title": "Enterprise Master Services Agreement (MSA)",
        "category": "MSA & NDA",
        "playbook_name": "Standard Corporate Playbook",
        "filename": "enterprise_master_services_msa.pdf",
        "text": """ENTERPRISE MASTER SERVICES AGREEMENT (MSA)

Section 1. Services, SLA Credits, and Payment Terms
Provider shall deliver enterprise managed services with 99.95% monthly uptime. Fees are payable Net 30 days from invoice date. Provider maintains commercial general liability and cyber insurance, and provides certificates of insurance upon 15 days written request.

Section 2. Limitation of Liability & Consequential Damages
Provider's aggregate liability shall be capped at one times (1x) fees paid in the preceding twelve (12) months; however, consequential and indirect damages shall be recoverable against Customer and are excluded solely for Vendor.

Section 3. Indemnification
Customer shall indemnify and hold harmless Provider against all claims whatsoever arising out of Customer's business operations, without limitation or monetary cap.

Section 4. Term, Auto-Renewal, and Termination Cure
This Agreement shall automatically renew for successive three-year terms without prior notice unless terminated 90 days before expiration. Provider may terminate immediately without cure period upon any invoice dispute.

Section 5. Governing Law & Precedence
This MSA is governed by the laws of the State of Delaware. Order of Precedence: In the event of conflict between this MSA and an executed SOW, this MSA shall prevail unless the SOW expressly overrides a named section.
""",
    },
    "saas": {
        "title": "ApexAI Enterprise SaaS Subscription Agreement",
        "category": "Cloud & SaaS",
        "playbook_name": "Standard Corporate Playbook",
        "filename": "apexai_enterprise_saas.pdf",
        "text": """APEXAI ENTERPRISE SAAS SUBSCRIPTION AGREEMENT

Section 1. Subscription Tiers and Payment Terms
Customer subscribes to the ApexAI Enterprise Tier. Annual subscription fees are payable Net 30 days.
| Tier | Annual Fee | SLA Uptime | Service Credit |
| --- | --- | --- | --- |
| Enterprise | $180,000 | 99.9% | 10% monthly credit |

Section 2. Proprietary Data & AI Model Training
Provider may retain and use Customer Data, inputs, and workflow logs to train and improve our artificial intelligence and machine learning models across all commercial tenants.

Section 3. Auto-Renewal and Liquidated Damages
Subscription terms automatically renew for successive two-year periods unless Customer gives notice 90 days prior without prior notice from Provider. Early cancellation triggers liquidated damages equal to 100% of remaining fees immediately accelerated.

Section 4. Termination, Audit & Security
Provider may terminate immediately without notice at its sole discretion. Customer may be audited at any time with unlimited audit access at Customer's sole expense. Upon termination, Provider will delete tenant data within 30 days upon written request.

Section 5. Governing Law
This Subscription Agreement is governed by the laws of the State of New York.
""",
    },
    "nda": {
        "title": "Mutual Confidentiality & Non-Disclosure Agreement (NDA)",
        "category": "MSA & NDA",
        "playbook_name": "Standard Corporate Playbook",
        "filename": "mutual_confidentiality_nda.pdf",
        "text": """MUTUAL CONFIDENTIALITY AND NON-DISCLOSURE AGREEMENT

Section 1. Definition of Confidential Information
Confidential Information includes all non-public technical, financial, roadmap, and customer data disclosed between the parties, excluding independently developed information.

Section 2. Non-Use, AI Training, and Subprocessor Sharing
Receiving Party shall protect Confidential Information using reasonable care; provided, however, Receiving Party may share data with any third-party subprocessor without prior notice and is shielded from liability for subprocessor leaks, and may utilize aggregated prompts to train machine learning models.

Section 3. Term, Notice, and Return of Materials
This Agreement shall automatically renew for successive two-year terms without prior notice unless terminated 90 days in advance. Within 30 days after written termination notice, Receiving Party shall return or destroy all Confidential Information and certify deletion in writing.

Section 4. Remedies and Attorney Fees
In any dispute regarding unauthorized disclosure, only Vendor shall recover all attorneys' fees regardless of outcome, and Customer waives any consequential damages exclusion.

Section 5. Governing Law
This Agreement shall be governed by the laws of the State of Delaware.
""",
    },
}
