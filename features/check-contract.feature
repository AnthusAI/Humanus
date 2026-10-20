@editorial @contracts
Feature: Check a document against a policy pack
  As a CMS copy-editing component
  I want one call that takes content plus a policy pack and returns an annotated document
  So that I can mark every policy problem on the draft the editor sees

  Scenario: Return an annotated document in UTF-16 offsets
    Given a check request for a Markus document with an emoji before its prose
    When Limatus checks the request
    Then the check result is a valid "check-result-v1" document
    And the check result reports offsets in "utf16" code units
    And every result segment's UTF-16 span selects its text as JavaScript would
    And the check result names the policy pack id and version
    And the check result includes one document segment and its paragraph and sentence segments
    And every lane reports a status

  Scenario: Reject an invalid check request
    Given a check request without content
    When Limatus checks the request
    Then checking fails with a check request validation error
    And the check request error names the location "content"

  Scenario: Check from the command line
    Given a check request file for a Markus document
    When I run the limatus command "check --request" with the request file
    Then the command succeeds
    And the command prints a valid "check-result-v1" document

  Scenario: A finding keeps its id when another sentence changes
    Given a finding for policy "no-hype" on "game-changing" in the sentence "This is game-changing work."
    When another sentence in the same paragraph is edited and the finding is identified again
    Then the finding id is unchanged

  Scenario: The same excerpt twice in a sentence gets two ids
    Given a finding for policy "no-hype" on "very" in the sentence "It is very, very good."
    When both occurrences of the excerpt are identified
    Then the two finding ids differ

  Scenario: Editing the sentence that holds the finding gives it a new id
    Given a finding for policy "no-hype" on "game-changing" in the sentence "This is game-changing work."
    When the sentence becomes "This is game-changing research." and the finding is identified again
    Then the finding id changes

  Scenario: Segments and findings carry plain text for rendered previews
    Given a check request whose pack flags "game-changing" in:
      """
      This **release** is *game-changing* for [teams](https://example.com) [@smith2020].
      """
    When Limatus checks the request
    Then the paragraph and sentence segments carry the plain text "This release is game-changing for teams."
    And the finding's excerpt text is "game-changing"
