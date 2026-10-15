"""Human-readable projections of saved assessments; no new fit claims or scores."""
HEADERS = ["Company", "Website", "Fit assessment", "Evidence supporting fit", "What needs checking",
           "Suggested next step", "Your decision", "Review note", "Service review", "Source links"]
FIT = {"fits": "Meets required criteria", "needs_verification": "Fit unverified", "does_not_fit": "Does not meet criteria"}
DECISION = {"accepted": "Accepted", "rejected": "Rejected", "needs_research": "Needs more research"}


def customer_tables(run, records):
    profile = run.get("profile") or {}
    criteria = {item["id"]: item["description"] for item in profile.get("criteria", [])}
    exclusions = {f"exclude-{i + 1}": item for i, item in enumerate(profile.get("exclusions", []))}
    summary, details = [], []
    for record in records:
        research = record["research"]
        first_detail = len(details)
        sources = {source["id"]: source for source in research["sources"]}
        positives, questions, negatives = [], [], []
        for kind, findings, labels, field in [
            ("Fit criterion", research["findings"], criteria, "criterion_id"),
            ("Exclusion", research.get("exclusion_findings", []), exclusions, "exclusion_id"),
        ]:
            for finding in findings:
                label = labels.get(finding[field], finding[field])
                status = finding["status"]
                if status == "unknown":
                    questions.append(("Exclusion check: " if kind == "Exclusion" else "") + label)
                    details.append([research["name"], kind, label, "Unknown", finding["reason"], "", "", "", ""])
                else:
                    if kind == "Fit criterion" and status == "supported":
                        positives.append(label)
                    if status in ("contradicted", "matched"):
                        negatives.append(label)
                    for evidence in finding["evidence"]:
                        source = sources.get(evidence["source_id"], {})
                        details.append([research["name"], kind, label, status.capitalize(), evidence["claim"],
                                        evidence["passage"], source.get("url", ""), source.get("retrieved_at", ""),
                                        source.get("published_at") or "Not provided"])
        for hypothesis in research.get("hypotheses", []):
            details.append([research["name"], "Hypothesis", "", "Unverified", hypothesis["text"],
                            "Assumptions: " + "; ".join(hypothesis["assumptions"]), "", "", ""])
        for source in sources.values():
            details.append([research["name"], "Source", "", "Saved page", source["title"], "", source["url"],
                            source.get("retrieved_at", ""), source.get("published_at") or "Not provided"])
        selection = next((item for item in run["checkpoint"].get("selection", []) if item["domain"] == research["domain"]), None)
        for signal in selection.get("signals", []) if selection else []:
            if signal["source_id"] in sources:
                details.append([research["name"], "Company activity", signal["label"], "Dated company statement",
                                "Event date: " + signal["event_date"] + ". First-party claim; buying intent unverified.",
                                signal["passage"], sources[signal["source_id"]]["url"], signal["observed_at"], ""])
        review = record.get("review") or {}
        operator = record.get("operator_review") or {}
        annotation = operator.get("annotation") or {}
        service = (f'{annotation.get("reviewer", "")}: {annotation.get("note", "")}' if annotation else "Not reviewed")
        if annotation:
            details.append([research["name"], "Service review", "", annotation["outcome"], service,
                            "Inspected sources: " + "; ".join(sources[source_id]["url"] for source_id in annotation.get("source_ids", []) if source_id in sources), "",
                            operator.get("reviewed_at", ""), ""])
        step = {"fits": "Review the evidence before deciding to pursue",
                "needs_verification": "Verify the open criteria before deciding to pursue",
                "does_not_fit": "Review the mismatch before excluding"}[research["qualification"]]
        if questions and negatives:
            checks = "Mismatch: " + "; ".join(negatives) + "\nUnverified: " + "; ".join(questions)
        else:
            checks = ("Mismatch: " + "; ".join(negatives) if negatives else "; ".join(questions)) or "; ".join(research.get("unknowns", [])) or "None recorded"
        for detail in details[first_detail:]:
            detail.append(research["domain"])
        summary.append([research["name"], "https://" + research["domain"], FIT[research["qualification"]],
                        "; ".join(positives) or "No supported fit criteria", checks, step,
                        DECISION.get(review.get("decision"), "Not reviewed"), review.get("reason", ""), service,
                        "\n".join(source["url"] for source in sources.values())])
    return summary, details
