@editorial @contracts @suggest
Feature: Rewrite suggestions for findings and selections
  As an editor looking at a flagged passage, or at any sentence I want to improve
  I want a few rewrite options that follow our policies and keep my facts
  So that I can fix the text with one click instead of rewriting it from scratch

  Background:
    Given a policy pack with a "no-hype" phrase rule for "game-changing" and rewrite guidance "Say what changed and by how much."
    And the draft:
      """
      # Release notes

      This release is game-changing for teams. Builds finish in 4 minutes instead of 9.
      """

  Scenario: Suggest rewrites for a finding
    Given the rewrite model will propose:
      | replacement                                        | rationale                    |
      | This release cuts build times for teams.           | Names the change.            |
      | This release halves build times for most teams.    | Quantifies it.               |
    When I ask for rewrites of the "no-hype" finding
    Then the suggest result is a valid "suggest-result-v1" document
    And there are 2 rewrite options
    And every option replaces the whole sentence that contains the finding
    And the rewrite prompt marked the flagged words inside the target
    And the rewrite prompt included the policy guidance and its rewrite guidance
    And the rewrite prompt included the surrounding paragraph
    And the rewrite prompt told the model not to add facts

  Scenario: Suggest rewrites for any selected sentence, with an editor note
    Given the rewrite model will propose:
      | replacement                     | rationale     |
      | Builds now take 4 minutes, not 9. | Shorter.    |
    When I select "Builds finish in 4 minutes instead of 9." and ask for rewrites with the note "shorter"
    Then there are 1 rewrite options
    And the suggest target is the selected text
    And the rewrite prompt included the editor note "shorter"

  Scenario: Options that change nothing or still break the rule are dropped
    Given the rewrite model will propose:
      | replacement                                     | rationale         |
      | This release is game-changing for teams.        | Same text.        |
      | This release is truly game-changing for teams.  | More emphasis.    |
      | This release cuts build times for teams.        | Names the change. |
    When I ask for rewrites of the "no-hype" finding
    Then there are 1 rewrite options
    And 2 options were dropped with reasons

  Scenario: Options whose rationale is about evading AI detection are dropped
    Given the rewrite model will propose:
      | replacement                              | rationale                                   |
      | This release cuts build times for teams. | Add slang so it sounds human to detectors.  |
    When I ask for rewrites of the "no-hype" finding
    Then there are 0 rewrite options
    And 1 options were dropped with reasons

  Scenario: A selection inside code or front matter is refused
    Given the draft:
      """
      Prose here.

      ```
      code here
      ```
      """
    When I select "code here" and ask for rewrites
    Then suggesting fails with a request error mentioning "prose"

  Scenario: Without a rewrite model the error says how to configure one
    Given no rewrite model is configured
    When I ask for rewrites of the "no-hype" finding
    Then suggesting fails with an unavailable error mentioning "OPENAI_API_KEY"

  Scenario: Draft classifier questions from a prose guideline
    Given the rewrite model will draft these detectors:
      | id            | scope    | instructions                                                    |
      | unearned-hype | sentence | Does the target sentence praise the product without evidence? |
      | broken        | page     | Not a valid scope.                                             |
    When I ask for classifier questions for the guideline "Do not hype the product; show evidence."
    Then the draft questions result is a valid "draft-questions-result-v1" document
    And 1 detector was drafted with default threshold 0.8 and review band from 0.5
    And the notes explain that "broken" was rejected
