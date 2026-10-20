@editorial @contracts @rules
Feature: Deterministic rules lane
  As an editor using a CMS that sends our policy pack to Humanus
  I want every phrase, pattern and built-in house rule checked on the prose I wrote
  So that rule-based problems are marked exactly where they occur, never in code or quotes

  Background:
    Given a policy pack with these rules policies:
      | policy        | severity | detector     | kind    | config                                      |
      | plain-words   | info     | utilize      | phrase  | phrases=utilize; replacement=use            |
      | no-hype       | warn     | hype         | regex   | pattern=\bgame[- ]chang\w*; ignoreCase      |
      | evidence      | error    | certainty    | builtin | check=unsupported_certainty                 |
      | contractions  | info     | contractions | builtin | check=uncontracted_forms                    |

  Scenario: Phrase rules flag whole words with the policy's severity and replacement
    Given the document to check is:
      """
      We utilize caching. We utilized it before.
      """
    When the document is checked
    Then the check result is a valid "check-result-v1" document
    And there is 1 finding for policy "plain-words"
    And that finding's excerpt is "utilize" with severity "info" and replacement "use"
    And every finding's UTF-16 span selects its excerpt
    And every finding sits in the sentence that contains it

  Scenario: Rules never fire inside code, links, quotes or directives
    Given the document to check is:
      """
      Read [the guide](https://example.com/utilize). Run `utilize()` first.

      > We utilize game-changing ideas.

      ::image{src="game-changing.png" alt="utilize"}

      ```
      utilize game-changing
      ```
      """
    When the document is checked
    Then there are no findings

  Scenario: Regex rules respect case options
    Given the document to check is:
      """
      This is a Game-Changing release.
      """
    When the document is checked
    Then there is 1 finding for policy "no-hype"
    And that finding's excerpt is "Game-Changing" with severity "warn"

  Scenario: Built-in sentence checks mark the whole sentence
    Given the document to check is:
      """
      Our approach is undeniably better. It ships on Tuesday.
      """
    When the document is checked
    Then there is 1 finding for policy "evidence"
    And that finding's excerpt is "Our approach is undeniably better." with severity "error"

  Scenario: Built-in checks can propose deterministic replacements
    Given the document to check is:
      """
      It is ready, and we do not need more time.
      """
    When the document is checked
    Then the findings for policy "contractions" have replacements "It's, don't"

  Scenario: Disabled policies produce no findings
    Given the document to check is:
      """
      We utilize caching. Our approach is undeniably better.
      """
    And policies "plain-words" and "evidence" are disabled
    When the document is checked
    Then there are no findings
    And the rules lane reports status "ran" with 2 detectors

  Scenario: Detectors can be limited to some blocks
    Given the document to check is:
      """
      # We utilize caching

      We utilize caching.
      """
    And detector "utilize" applies only to "heading" blocks
    When the document is checked
    Then there is 1 finding for policy "plain-words"
    And that finding is in a "heading" block

  Scenario: Findings keep their ids when other paragraphs change
    Given the document to check is:
      """
      We utilize caching.

      Another paragraph.
      """
    When the document is checked
    And the second paragraph is replaced with "A rewritten paragraph." and the document is checked again
    Then the "plain-words" finding has the same id in both results

  Scenario: The AI-writing tells starter pack flags its own examples
    When I load the built-in policy pack "ai-writing-tells"
    Then it is a valid policy pack
    And every policy's violating examples produce a finding for that policy
    And no policy's complying examples produce any finding

  Scenario: List the built-in starter packs from the command line
    When I run the humanus command "pack builtin"
    Then the command succeeds
    And the command output lists "ai-writing-tells"
