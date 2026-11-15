"""Benchmark deal templates (ma, cloud_dpa, joint_ip, msa, saas, nda) for instant demo ingestion."""

from __future__ import annotations

DEMO_CONTRACTS: dict[str, dict[str, str]] = {
    "ma": {
        "title": "Apex Cloud Acquisition — Share & Asset Purchase Agreement",
        "filename": "apex_ma_acquisition_2026.pdf",
        "playbook": "Strict M&A & IP Playbook",
        "category": "M&A & IP",
        "text": (
            "Section 1. Transaction Scope & Purchase Consideration\n"
            "Buyer agrees to acquire the target cloud assets for $48,000,000 payable in two tranches. "
            "Buyer shall pay all undisputed closing invoices net 30 days from invoice date.\n\n"
            "Section 2. Indemnification & Unlimited Seller Exposure\n"
            "Seller shall provide unlimited indemnification and hold Buyer harmless without any cap or limitation against all claims whatsoever arising from pre-closing IP disputes, tax audits, or regulatory fines.\n\n"
            "Section 3. Consequential & Indirect Damages\n"
            "In the event of a breach of fundamental representations, Seller shall be liable for all indirect, consequential, incidental, and punitive damages, including lost profits and diminution in enterprise value.\n\n"
            "Section 4. Non-Compete & Worldwide Exclusivity\n"
            "Seller and its affiliates agree to a perpetual non-compete and worldwide exclusivity covenant and shall not engage with any competing provider globally for five years following the Closing Date.\n\n"
            "Section 5. Attorneys' Fees & Governing Law\n"
            "Customer shall solely reimburse Seller's attorneys' fees regardless of the outcome of any escrow dispute. "
            "This Agreement shall be governed by the laws of the State of Delaware. All written notice of claims must be delivered within 15 days of discovery."
        ),
    },
    "cloud_dpa": {
        "title": "Global Data Processing Addendum (GDPR & AI Governance DPA)",
        "filename": "global_cloud_dpa_2026.pdf",
        "playbook": "Enterprise SaaS Vendor Playbook",
        "category": "Cloud & SaaS",
        "text": (
            "Section 1. Processing Scope & AI Prohibition\n"
            "Processor shall process Personal Data strictly in accordance with Controller's documented instructions. "
            "Processor shall not train AI or machine learning models on Customer Personal Data.\n\n"
            "Section 2. Subprocessor Authorization & Liability Shield\n"
            "Processor may engage any subprocessor without prior notice to Controller and Processor assumes no liability for acts or omissions of subprocessors located outside the EEA.\n\n"
            "Section 3. Security Audits & Compliance Certifications\n"
            "Processor maintains annual SOC 2 Type II and ISO 27001 certification. Controller retains unlimited right to audit and inspect all facilities without prior notice at any time.\n\n"
            "Section 4. Data Deletion & Breach Notification\n"
            "Processor shall delete and purge all Customer Data within 30 days after termination of the underlying services. "
            "Processor shall provide written notice of any confirmed Personal Data breach within 48 hours of discovery.\n\n"
            "Section 5. Liability Cap & Governing Law\n"
            "Notwithstanding any other agreement, Processor's aggregate liability under this DPA shall not exceed $50,000 in total. "
            "This DPA shall be governed by the laws of England and Wales."
        ),
    },
    "joint_ip": {
        "title": "Joint AI Co-Development & Intellectual Property Agreement",
        "filename": "joint_ip_codev_2026.pdf",
        "playbook": "Strict M&A & IP Playbook",
        "category": "M&A & IP",
        "text": (
            "Section 1. Co-Development Deliverables & Fees\n"
            "Parties will jointly engineer domain-specific legal reasoning modules. Development milestones are payable net 45 days from milestone acceptance.\n\n"
            "Section 2. Model Training & Data Ownership\n"
            "Partner is granted a perpetual royalty-free license to all inputs and Customer Data and may train its proprietary artificial intelligence models on any datasets uploaded during joint testing.\n\n"
            "Section 3. Exclusivity & Non-Compete Covenant\n"
            "Enterprise shall grant Partner worldwide exclusivity for enterprise legal workflows and shall not engage with any competing provider for five years.\n\n"
            "Section 4. Liquidated Damages & Termination\n"
            "Upon early cancellation for convenience, Enterprise shall pay liquidated damages equal to 200% of all remaining fees and suffer forfeiture of all prepaid fees. "
            "Partner may terminate this Agreement immediately without notice or cure period upon any suspected breach.\n\n"
            "Section 5. Governing Law & Insurance\n"
            "Partner shall maintain $5,000,000 in Cyber Liability and Errors and Omissions insurance coverage and deliver a certificate of insurance within 15 days of Effective Date. "
            "This Agreement is governed by the laws of the State of New York."
        ),
    },
    "msa": {
        "title": "Enterprise Master Services Agreement (MSA-2026)",
        "filename": "enterprise_msa_2026.pdf",
        "playbook": "Standard Corporate Playbook",
        "category": "MSA & NDA",
        "text": (
            "Section 1. Services & Payment Terms\n"
            "Vendor shall deliver enterprise platform implementation and managed support services. "
            "Customer shall pay all undisputed invoices net 30 days from invoice date.\n\n"
            "Section 2. Limitation of Liability & Indemnification\n"
            "Vendor's aggregate liability under this Master Agreement shall not exceed twelve (12) months of fees paid. "
            "However, Customer shall provide uncapped indemnification without any cap or limitation for third-party regulatory claims arising from Customer configurations.\n\n"
            "Section 3. Consequential Damages\n"
            "Section 3.1 shall not exclude consequential or indirect damages, and Customer shall be liable for all indirect and consequential damages including lost profits.\n\n"
            "Section 4. Term, Auto-Renewal & Termination\n"
            "This Agreement shall automatically renew for successive one-year terms unless terminated with 90 days prior written notice. "
            "Vendor may terminate immediately without cure period upon any late invoice or suspected breach.\n\n"
            "Section 5. Security Audit, Insurance & Governing Law\n"
            "Vendor shall maintain SOC 2 Type II compliance and Commercial General Liability insurance within 15 days of Effective Date. "
            "Order of precedence: This MSA governs over any SOW unless expressly amended. Governed by the laws of the State of New York."
        ),
    },
    "saas": {
        "title": "Enterprise AI SaaS Subscription Agreement (Order Form & SLA)",
        "filename": "enterprise_ai_saas_2026.pdf",
        "playbook": "Enterprise SaaS Vendor Playbook",
        "category": "Cloud & SaaS",
        "text": (
            "Section 1. Cloud Subscription & SLA Service Credits\n"
            "Provider guarantees 99.9% availability monthly uptime. Customer may claim service credits within 15 days of monthly SLA breach.\n\n"
            "Section 2. AI Model Training & Telemetry Rights\n"
            "Provider may use Customer Data to improve artificial intelligence algorithms and train its proprietary AI models across multi-tenant clusters.\n\n"
            "Section 3. Subprocessors & Data Deletion\n"
            "Provider may engage any subprocessor without prior notice and disclaims liability for subprocessors. "
            "Upon expiration, Provider will delete Customer Data within 30 days after termination.\n\n"
            "Section 4. Auto-Renewal & Liquidated Penalties\n"
            "Subscription shall automatically renew for successive two-year terms unless non-renewal notice is sent 120 days prior. "
            "Early termination triggers liquidated damages equal to 200% of all remaining fees.\n\n"
            "Section 5. Liability Cap & Governing Law\n"
            "Provider's aggregate liability shall not exceed 2x annual subscription fees. Governed by the laws of the State of California."
        ),
    },
    "nda": {
        "title": "Mutual Strategic Non-Disclosure & Evaluation Agreement",
        "filename": "strategic_mutual_nda_2026.pdf",
        "playbook": "Standard Corporate Playbook",
        "category": "MSA & NDA",
        "text": (
            "Section 1. Purpose & Confidential Information\n"
            "The Parties wish to exchange proprietary technical architecture, pricing schedules, and roadmap data for evaluating a strategic partnership.\n\n"
            "Section 2. AI Evaluation & Residuals\n"
            "Receiving Party shall not train machine learning models on Disclosing Party's Confidential Information; however, Receiving Party is granted a perpetual license to inputs submitted to evaluation sandboxes.\n\n"
            "Section 3. Audit & Fee Shifting\n"
            "Disclosing Party retains unlimited audit rights to inspect all facilities without prior notice. "
            "Customer shall solely reimburse Disclosing Party's attorneys' fees regardless of the outcome of any injunctive proceeding.\n\n"
            "Section 4. Return or Destruction & Notice\n"
            "Upon written request, Receiving Party shall destroy or return all Confidential Information within 15 days and provide written notice certifying deletion.\n\n"
            "Section 5. Governing Law\n"
            "This Agreement shall be governed by the laws of the State of Delaware."
        ),
    },
}
