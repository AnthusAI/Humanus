@editorial @contracts @rules @standards
Feature: Built-in checks for standard rule sets
  As a publication adopting a writing standard such as Simplified Technical English
  or the Federal Plain Language Guidelines
  I want the standard's mechanical rules available as configurable built-in checks
  So that a policy pack can enforce them with the limits the standard sets

  Scenario: Sentences over a word limit are flagged with their length
    Given a built-in "sentence_length" check with params {"maxWords": 8}
    And the document to check is:
      """
      This short sentence is fine. This sentence has far too many words in it for the limit.
      """
    When the document is checked
    Then the built-in findings are on "This sentence has far too many words in it for the limit."
    And the first finding's message mentions "12 words"

  Scenario: Procedure and description sentences get their own limits
    Given a built-in "sentence_length" check with params {"maxWords": 6, "topic": "procedure"}
    And the document to check is:
      """
      The pump moves oil from the tank to the engine every minute.

      1. Remove the filter cover from the filter housing slowly.
      """
    When the document is checked
    Then the built-in findings are on "Remove the filter cover from the filter housing slowly."

  Scenario: The average sentence length of the document is checked
    Given a built-in "average_sentence_length" check with params {"maxWords": 5}
    And the document to check is:
      """
      The committee will review every application it receives this year. It will publish the results.
      """
    When the document is checked
    Then there is 1 built-in finding covering the whole document

  Scenario: Long paragraphs are flagged
    Given a built-in "paragraph_length" check with params {"maxSentences": 2}
    And the document to check is:
      """
      One. Two. Three.

      Four. Five.
      """
    When the document is checked
    Then the built-in findings are on "One. Two. Three."

  Scenario: A document above the reading grade level is flagged
    Given a built-in "reading_grade_level" check with params {"maxGrade": 6, "minWords": 10}
    And the document to check is:
      """
      Notwithstanding the aforementioned considerations, organizational stakeholders must operationalize comprehensive accountability frameworks immediately.
      """
    When the document is checked
    Then there is 1 built-in finding covering the whole document
    And the first finding's message mentions "grade"

  Scenario: Double negatives are flagged
    Given a built-in "double_negative" check with params {}
    And the document to check is:
      """
      It is not uncommon for applicants to wait. You do not need nothing else. It is common.
      """
    When the document is checked
    Then the built-in findings are on "not uncommon | not need nothing"

  Scenario: Acronyms used before they are defined are flagged once
    Given a built-in "undefined_acronym" check with params {}
    And the document to check is:
      """
      Send the form to the FAA today. The Social Security Administration (SSA) will reply. The SSA is busy. The FAA is too.
      """
    When the document is checked
    Then the built-in findings are on "FAA"

  Scenario: A procedure step with two instructions is flagged
    Given a built-in "multiple_instructions" check with params {}
    And the document to check is:
      """
      1. Remove the cover and clean the filter.
      2. Install the cover.
      """
    When the document is checked
    Then the built-in findings are on "Remove the cover and clean the filter."

  Scenario: A procedure step that does not start with a verb is flagged
    Given a built-in "imperative_steps" check with params {}
    And the document to check is:
      """
      1. Remove the cover.
      2. The operator cleans the filter.
      """
    When the document is checked
    Then the built-in findings are on "The operator cleans the filter."

  Scenario: -ing verb forms are flagged but technical -ing nouns are allowed
    Given a built-in "ing_form" check with params {"allow": ["housing", "warning"]}
    And the document to check is:
      """
      Before installing the housing, read the warning.
      """
    When the document is checked
    Then the built-in findings are on "installing"

  Scenario: A singular noun that starts a sentence without an article is flagged
    Given a built-in "missing_article" check with params {"nouns": ["filter", "cover"]}
    And the document to check is:
      """
      Filter is dirty. The cover is clean.
      """
    When the document is checked
    Then the built-in findings are on "Filter"

  Scenario: A word used outside its one approved meaning is flagged
    Given a built-in "one_meaning" check with params {"words": [{"word": "check", "meaning": "verb"}, {"word": "power", "meaning": "noun"}]}
    And the document to check is:
      """
      Do a check of the oil. Check the oil. Power the unit. Set the power switch.
      """
    When the document is checked
    Then the built-in findings are on "check | Power"

  Scenario: Phrase detectors skip matches inside protected technical names
    Given a phrase detector for "housing" with the exception "filter housing"
    And the document to check is:
      """
      Clean the filter housing. Replace the housing.
      """
    When the document is checked
    Then the built-in findings are on "housing"
    And the only finding starts after "Replace the "

  Scenario: Passive voice with irregular participles is flagged
    Given a built-in "passive_voice" check with params {}
    And the document to check is:
      """
      The repair was made yesterday. The team made the repair.
      """
    When the document is checked
    Then the built-in findings are on "The repair was made yesterday."
