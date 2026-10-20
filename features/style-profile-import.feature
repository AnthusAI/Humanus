@editorial @contracts
Feature: Import a style profile as a policy pack
  As a publication moving from style profiles to policy packs
  I want my existing style profile converted into an equivalent policy pack
  So that I keep my house rules without rewriting them by hand

  Scenario: Convert every profile control into policies
    Given a style profile fixture with checks and rules
    When the style profile is imported as a policy pack
    Then the imported pack is a valid "policy-pack-v1" document
    And the imported pack id is the profile's publication key
    And the avoid lexicon becomes a policy with a "phrase" detector
    And each banned pattern becomes a "regex" detector that keeps its message
    And each enabled check becomes a "builtin" detector
    And tone, sentence style and evidence rules become guidance-only policies
    And the reference samples are embedded with their text

  Scenario: Import from the command line
    When I run the humanus command "pack import --profile features/fixtures/policy-pack/style-profile.yml"
    Then the command succeeds
    And the command prints a valid "policy-pack-v1" document
