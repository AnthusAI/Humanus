@editorial @contracts @rules
Feature: Table prose is checked and quotations are exempt
  As an editor whose stories keep central claims in tables and quote other people
  I want table cells checked like any other prose, and direct quotations left alone by rules
  So that table claims are not missed and a source's own words are not marked as violations

  Background:
    Given a policy pack with these rules policies:
      | policy       | severity | detector     | kind    | config                                  |
      | plain-words  | info     | utilize      | phrase  | phrases=utilize; replacement=use        |
      | passive      | warn     | passive      | builtin | check=passive_voice                     |
      | contractions | info     | contractions | builtin | check=uncontracted_forms                |
      | placeholders | error    | placeholder  | regex   | pattern=\bTODO\b; quotations=check      |

  Scenario: Rules read table cells and report spans in the original document
    Given the document to check is:
      """
      Intro text.

      | Option | Why |
      |:-------|----:|
      | Cache  | We utilize it. |
      | Count  | 1,200 |
      | Call   | `utilize()` |
      """
    When the document is checked
    Then the check result is a valid "check-result-v1" document
    And there is 1 finding for policy "plain-words"
    And that finding's excerpt is "utilize" with severity "info" and replacement "use"
    And that finding is in a "tableCell" block
    And every finding's UTF-16 span selects its excerpt
    And every finding sits in the sentence that contains it
    And no finding excerpt contains table syntax
    And the check result has no protected regions

  Scenario: Table spans stay exact after emoji and surrogate pairs
    Given the document to check is:
      """
      | 😀 | Note |
      |---|---|
      | 😀😀 | We utilize it. |
      """
    When the document is checked
    Then there is 1 finding for policy "plain-words"
    And every finding's UTF-16 span selects its excerpt

  Scenario: A request can turn table checking off
    Given the document to check is:
      """
      | Option | Why |
      |--------|-----|
      | Cache  | We utilize it. |
      """
    When the document is checked with table checking off
    Then there are no findings
    And the check result has protected regions "table"

  Scenario: Table cells do not skew whole-document measures
    Given a policy pack with these rules policies:
      | policy   | severity | detector | kind    | config                           |
      | brevity  | warn     | average  | builtin | check=average_sentence_length    |
    And the average sentence length limit is 3 words
    And the document to check is:
      """
      | A | B |
      |---|---|
      | one two three four five six seven eight | nine ten eleven twelve |

      Short one here.
      """
    When the document is checked
    Then there are no findings

  Scenario: Quoted sentences are not reported for passive voice or uncontracted forms
    Given the document to check is:
      """
      The mayor said, "The report was written last night. We do not utilize it."

      The report was written last night. We do not agree.
      """
    When the document is checked
    Then the findings are, by policy and excerpt:
      | policy       | excerpt                            |
      | passive      | The report was written last night. |
      | contractions | do not                             |

  Scenario: A passive clause inside a quotation does not make the surrounding sentence passive
    Given the document to check is:
      """
      She said "mistakes were made" and left.
      """
    When the document is checked
    Then there are no findings

  Scenario: Curly quotation marks exempt too
    Given the document to check is:
      """
      He wrote, “We do not utilize it.” Nothing else follows.
      """
    When the document is checked
    Then there are no findings

  Scenario: A detector can opt back in to checking quotations
    Given detector "utilize" checks quotations
    And the document to check is:
      """
      The mayor said, "We utilize it."
      """
    When the document is checked
    Then there is 1 finding for policy "plain-words"

  Scenario: A policy can opt back in
    Given policy "plain-words" checks quotations
    And the document to check is:
      """
      The mayor said, "We utilize it."
      """
    When the document is checked
    Then there is 1 finding for policy "plain-words"

  Scenario: A detector can opt out again when its policy opts in
    Given policy "plain-words" checks quotations
    And detector "utilize" exempts quotations
    And the document to check is:
      """
      The mayor said, "We utilize it."
      """
    When the document is checked
    Then there are no findings

  Scenario: Placeholder leaks still fire inside quotations
    Given the document to check is:
      """
      The mayor said, "Call TODO about it."
      """
    When the document is checked
    Then there is 1 finding for policy "placeholders"

  Scenario: Chatbot artifacts and placeholder leaks in the starter pack still fire in quotations
    Given the built-in policy pack "ai-writing-tells" is loaded
    When the document is checked with the built-in pack:
      """
      The editor wrote, "I hope this helps. Replace [Company Name] here."
      """
    Then the findings include policies "chatbot-artifacts, placeholder-leaks"

  Scenario: Quotations in table cells are exempt too
    Given the document to check is:
      """
      | Who   | Said |
      |-------|------|
      | Mayor | "We do not utilize it." |
      | Clerk | We do not utilize it. |
      """
    When the document is checked
    Then the findings are, by policy and excerpt:
      | policy       | excerpt |
      | contractions | do not  |
      | plain-words  | utilize |
    And every finding sits in the "Clerk" row
