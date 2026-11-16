@editorial @measure
Feature: Basic content measurements
  As an editor, or an agent working for one
  I want plain numbers about a draft: how long it is, how it is built, how well it is sourced and how much a revision changed
  So that I have something to judge a piece by before and after I edit it

  Measurements are guidance, never gates. Humanus reports numbers and sets no limits, passes nothing and fails nothing.
  They are deterministic: the same text and language always give the same numbers, and no model is called.
  Every measurement reads the text the way its language pack does: words in English and Spanish, characters in Simplified Chinese.

  Scenario: Size counts words and gives a reading time
    Given the language is "en"
    And the text to measure is:
      """
      # A short story

      Cats sleep most of the day. They wake at dusk.

      Dogs do not.
      """
    When the text is measured
    Then the size unit is "word"
    And the size is 16 units
    And the reading time is a positive number of minutes

  Scenario: Simplified Chinese counts characters, not words
    Given the language is "zh-Hans"
    And the text to measure is:
      """
      猫整天睡觉。它们在黄昏醒来。
      """
    When the text is measured
    Then the size unit is "character"
    And the size is 12 units

  Scenario: Reading time follows the language pack's reading rate
    Given the language is "en"
    And the text to measure is 476 repeated words
    When the text is measured
    Then the reading time is 2.0 minutes

  Scenario: Code, directives and front matter are not read
    Given the language is "en"
    And the text to measure is:
      """
      ---
      title: Hidden words here
      ---

      Three plain words.

      ```
      code is not prose at all
      ```

      :::callout
      Two words.
      :::
      """
    When the text is measured
    Then the size is 5 units

  Scenario: A quotation is read, so a story built on quotations is not undercounted
    Given the language is "en"
    And the text to measure is:
      """
      She said:

      > We will not go.
      """
    When the text is measured
    Then the size is 6 units

  Scenario: Structure counts sections and finds the longest paragraph and sentence
    Given the language is "en"
    And the text to measure is:
      """
      # Title

      One two three.

      ## Part

      One two three four five six. Seven eight.

      - A list item of five words.
      """
    When the text is measured
    Then the structure has 2 sections
    And the structure has 2 paragraphs
    And the longest paragraph is 8 units
    And the longest sentence is 6 units

  Scenario: The headline, dek and blurb are measured when given
    Given the language is "en"
    And the text to measure is "Body text."
    And the headline is "Cats win"
    And the dek is empty
    When the text is measured
    Then the headline is present with length 2
    And the dek is absent
    And the blurb is not measured

  Scenario: Sourcing counts links and citations per 500 words
    Given the language is "en"
    And the text to measure is:
      """
      A claim with [a link](https://example.com/a) in it. [@smith2020]

      Another paragraph with no source at all.

      A third cites [@a; @b] together.
      """
    When the text is measured
    Then there are 4 sources in the text: 1 links and 3 citations
    And the share of paragraphs without a source is 0.3333
    And the sources per 500 units are close to 111.1

  Scenario: A paragraph that uses a reference-style link is sourced
    Given the language is "en"
    And the text to measure is:
      """
      A claim with [a link][one] in it.

      [one]: https://example.com/one
      """
    When the text is measured
    Then the share of paragraphs without a source is 0.0

  Scenario: Text with no words has no per-word figures
    Given the language is "en"
    And the text to measure is empty
    When the text is measured
    Then the size is 0 units
    And the sources per 500 units are not defined

  Scenario: Measuring is deterministic
    Given the language is "es"
    And the text to measure is "Hola mundo. ¿Cómo estás?"
    When the text is measured twice
    Then both measurements are identical

  Scenario: A language with no pack is refused
    Given the language is "fr"
    And the text to measure is "Bonjour."
    When the text is measured
    Then measuring is refused naming "fr"

  Scenario: Concept density is not part of this slice
    Given the language is "en"
    And the text to measure is "Body text."
    When the text is measured with a concept list
    Then measuring is refused because concepts are not supported yet

  Scenario: Change size counts words added, removed and rewritten
    Given the language is "en"
    When the change from "The cat sat on the mat today." to "The dog sat on the rug and slept." is measured
    Then the change has 3 rewritten, 1 added, 0 removed and 4 unchanged

  Scenario: Identical text changed nothing
    Given the language is "en"
    When the change from "Same words here." to "Same  words here." is measured
    Then the change share is 0.0

  Scenario: Markup alone is not a change
    Given the language is "en"
    When the change from "A plain claim." to "A **plain** [claim](https://example.com)." is measured
    Then the change share is 0.0

  Scenario: Replacing everything changes all of it
    Given the language is "en"
    When the change from "One two three." to "Four five six." is measured
    Then the change share is 1.0

  Scenario: Pure additions and removals
    Given the language is "en"
    When the change from nothing to "Brand new text." is measured
    Then the change has 0 rewritten, 3 added, 0 removed and 0 unchanged
    And the change share is 1.0

  Scenario: Change size in Chinese counts characters
    Given the language is "zh-Hans"
    When the change from "猫睡觉。" to "狗睡觉。" is measured
    Then the change has 1 rewritten, 0 added, 0 removed and 2 unchanged
    And the change unit is "character"

  Scenario: The command line prints the same measurements
    Given the language is "en"
    And the text to measure is "Three plain words."
    When the text is measured on the command line
    Then the command succeeds and prints a size of 3 units

  Scenario: The command line compares two files
    Given the language is "en"
    When two files are compared on the command line
    Then the command succeeds and prints a share changed of 1.0
