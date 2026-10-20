@editorial @contracts
Feature: Policy packs are the editorial contract
  As a CMS integrating Humanus
  I want to send my editorial policies as a validated policy pack
  So that Humanus enforces our guidelines without reading files from disk

  Scenario: Load a policy pack from a payload
    Given a policy pack payload with a rules policy and a classifier policy
    When the policy pack payload is loaded
    Then the loaded pack has the policies "no-hype" and "concrete-claims"
    And policy "no-hype" has a "rules" detector of kind "phrase"
    And policy "concrete-claims" has a "classifier" detector with scope "sentence"
    And each loaded policy keeps its version and severity

  Scenario: Accept a guidance-only policy
    Given a policy pack payload with a guidance-only policy
    When the policy pack payload is loaded
    Then the loaded policy "plain-language" has no detectors

  Scenario: Reject a classifier detector without a question
    Given a policy pack payload whose classifier detector has no question
    When the policy pack payload is loaded
    Then loading fails with a policy pack validation error
    And the policy pack error names the location "policies/1/detectors/0"

  Scenario: Reject duplicate policy ids
    Given a policy pack payload with two policies named "no-hype"
    When the policy pack payload is loaded
    Then loading fails with a policy pack validation error
    And the policy pack error mentions "duplicate policy id 'no-hype'"

  Scenario: Reject a regex detector that does not compile
    Given a policy pack payload with the regex pattern "(unclosed"
    When the policy pack payload is loaded
    Then loading fails with a policy pack validation error
    And the policy pack error mentions "does not compile"

  Scenario Outline: Publish each contract schema
    When I run the humanus command "schema <name>"
    Then the command succeeds
    And the command prints a JSON Schema whose id ends with "<name>.json"

    Examples:
      | name               |
      | policy-pack-v1     |
      | check-request-v1   |
      | check-result-v1    |
      | suggest-request-v1 |
      | suggest-result-v1  |
