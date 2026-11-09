# cheque_bounce_followup (multi_turn)
Model: gemini:gemini-3.5-flash
Expected: NI Act s.138 with its notice timeline from the retrieved text; keeps context across turns

## User
My friend gave me a cheque of Rs 50,000 to repay a loan and it bounced.
## Agent: banking
## Clarifying questions the app would ask (not answered in this batch run)
- Do you have the cheque return memo from your bank?
- When was the cheque returned by the bank?
- Have you sent a legal notice to your friend yet?

## Assistant
**Where you stand**
*   A cheque dishonour makes the drawer liable to compensate you, provided you give them proper notice of the dishonour [1].
*   A cheque is considered dishonoured when the drawee bank defaults in payment upon being required to pay [2].
*   You can file a formal complaint in court for the offence of cheque dishonour [3].

**What to do**
1.  **Demand Payment:** Send a formal legal notice to your friend demanding the payment within 15 days of receiving the cheque return memo from the bank.
2.  **File Complaint:** If they do not pay within 15 days of receiving your notice, file a criminal complaint under Section 138 of the Negotiable Instruments Act in the court having jurisdiction over your bank branch [3].
3.  **Seek Compensation:** During the court case, you may request the court to direct the drawer to pay interim compensation of up to 20% of the cheque amount [4].

**Keep as proof**
The original cheque, the bank's cheque return memo, and a copy of the legal notice with the postal receipt.

**See a lawyer if**
You need to draft the legal notice or file the court complaint, as strict timelines apply.

Sources (official text, India Code):
  [1] The Negotiable Instruments Act, 1881, Section 30 (Liability of drawer.) https://indiacode.gov.in/handle/123456789/535767
  [2] The Negotiable Instruments Act, 1881, Section 92 (Dishonour by non-payment.) https://indiacode.gov.in/handle/123456789/535832
  [3] The Negotiable Instruments Act, 1881, Section 142 (Cognizance of offences.) https://indiacode.gov.in/handle/123456789/535888
  [4] The Negotiable Instruments Act, 1881, Section 143A (Power to direct interim compensation.) https://indiacode.gov.in/handle/123456789/538062

Checker notes:
  - Mentions 'Section 138' which is not among the retrieved sources; treat it as unverified.

This is legal information, not legal advice. For your specific case, consult a lawyer or free legal aid (NALSA 15100).
<details><summary>Retrieved sources</summary>

- negotiable_instruments_act_1881__s84 (When cheque not duly presented and drawer damaged thereby.) score=0.0872
- negotiable_instruments_act_1881__s143A (Power to direct interim compensation.) score=0.0839
- negotiable_instruments_act_1881__s30 (Liability of drawer.) score=0.0799
- banning_of_unregulated_deposit_schemes_act_2019__s2 (Definitions.) score=0.078
- negotiable_instruments_act_1881__s131 (Non-liability of banker receiving payment of cheque.) score=0.0757
- negotiable_instruments_act_1881__s92 (Dishonour by non-payment.) score=0.073
- negotiable_instruments_act_1881__s142 (Cognizance of offences.) score=0.0725
- banning_of_unregulated_deposit_schemes_act_2019__s21 (Punishment for contravention of section 3.) score=0.0715

Rewrite: {"summary": "The user is seeking legal recourse for a cheque bounce regarding a loan repayment of Rs 50,000.", "queries": ["dishonour of cheque for insufficiency of funds", "legal notice for cheque bounce", "offence of dishonour of cheque", "penalties for cheque bounce"], "areas": ["banking", "contract_money"]}
</details>

## User
The bank returned it 10 days ago. Is there a deadline for me to do something?
## Agent: banking
## Clarifying questions the app would ask (not answered in this batch run)

## Assistant
**Where you stand**
*   You must send a written demand notice to the drawer within 30 days of receiving the cheque return memo from your bank [1].
*   Once the drawer receives this notice, they have 15 days to pay the amount [1].
*   If they fail to pay within those 15 days, you have 30 days from the expiry of that period to file a court complaint [1].

**What to do**
1.  **Send Notice Immediately:** Since 10 days have already passed, send a formal legal notice via registered post right away to ensure it reaches them within the 30-day limit from the return memo date.
2.  **Track Delivery:** Keep the tracking receipt to prove when the notice was delivered.
3.  **Wait 15 Days:** If payment is not received within 15 days of their receipt of the notice, proceed to file a complaint in court.

**Keep as proof**
The bank's cheque return memo and the postal receipt of the legal notice.

**See a lawyer if**
You are unsure about the 30-day calculation or need help drafting the notice.

This is legal information, not legal advice. For your specific case, consult a lawyer or free legal aid (NALSA 15100).
<details><summary>Retrieved sources</summary>

- negotiable_instruments_act_1881__s143A (Power to direct interim compensation.) score=0.1039
- negotiable_instruments_act_1881__s84 (When cheque not duly presented and drawer damaged thereby.) score=0.0889
- negotiable_instruments_act_1881__s138 (Dishonour of cheque for insufficiency, etc., of funds in the account.) score=0.0641
- banking_regulation_act_1949__s47A (Power of Reserve Bank to impose penalty) score=0.0634
- reserve_bank_of_india_act_1934__s58G (Power of Bank to impose fine.) score=0.0611
- negotiable_instruments_act_1881__s89 (Payment of instrument on which alteration is not apparent.) score=0.0568
- reserve_bank_of_india_act_1934__s45MC (Power of Bank to file winding up petition.) score=0.0568
- banning_of_unregulated_deposit_schemes_act_2019__s2 (Definitions.) score=0.055

Rewrite: {"summary": "The user is seeking information regarding the legal time limits and procedures for initiating action after a cheque issued for loan repayment was dishonoured by the bank.", "queries": ["legal notice for dishonour of cheque", "time limit for filing complaint for cheque bounce", "procedure for cheque return due to insufficient funds", "legal action for recovery of money after cheque bounce"], "areas": ["banking", "contract_money"]}
</details>
