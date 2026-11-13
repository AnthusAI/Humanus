@multilingual
Feature: Rules are written once and take their words from the language
  As a policy author, I want rules written once with the language supplying its own words,
  units and native rates, so Spanish and Chinese packs are data and not branches in the engine.
  (Kanbus LIM-3307d3, first part)

  Scenario: A density rule compares with what native writers do
    Given the "zh-Hans" language pack records how often native writing uses the passive marker "被"
    And a "zh-Hans" policy that flags a paragraph using "passiveMarkers" far more often than that
    And a draft in "zh-Hans":
      """
      这名男子被警察拦下，车辆被拖走，手机被没收，证件被扣留，他本人也被带回派出所接受询问。事后警方说明这是一次例行检查，并无其他原因，请大家不要猜测，也不要转发未经核实的传言和消息。
      """
    When Humanus checks it with that policy
    Then the paragraph is reported with the message containing "5 times in 80 characters (62.5 per 1,000)"
    And the message names the native rate "1 per 1,000"

  Scenario: One passive in a paragraph is not reported
    Given a "zh-Hans" policy that flags a paragraph using "passiveMarkers" far more often than that
    And a draft in "zh-Hans":
      """
      他的建议被采纳了，团队随后调整了发布计划。
      """
    When Humanus checks it with that policy
    Then no finding is reported

  Scenario: A frame is found across a gap inside one sentence
    Given a "zh-Hans" policy for the frame "不是 … 而是"
    And a draft in "zh-Hans":
      """
      这不是一次简单的实验，而是一场深刻的变革。
      """
    When Humanus checks it with that policy
    Then exactly one finding is reported, with the excerpt "不是一次简单的实验，而是"

  Scenario: A Spanish frame matches on word boundaries
    Given a "es" policy for the frame "no solo … sino"
    And a draft in "es":
      """
      No solo es rápido, sino también barato. El sinónimo no solo sinodal.
      """
    When Humanus checks it with that policy
    Then exactly one finding is reported, with the excerpt "No solo es rápido, sino"

  Scenario: Length is counted in the language's own unit
    Given a "zh-Hans" policy that limits sentences to 10 units
    And a draft in "zh-Hans":
      """
      研究人员在四座城市测试了这套系统。好。
      """
    When Humanus checks it with that policy
    Then exactly one finding is reported, with the message "Sentence has 16 characters; the limit is 10."

  Scenario: A rule the language cannot run is named, not skipped in silence
    Given a "zh-Hans" policy that needs the word class tagged "pronoun"
    And a draft in "zh-Hans":
      """
      他认为它是重要的。
      """
    When Humanus checks it with that policy
    Then the rules lane names the policy as not run because "no part-of-speech tagger"
    And no finding is reported

  Scenario: An English built-in check is not run on Chinese
    Given a language-neutral policy that uses the built-in check "passive_voice"
    And a draft in "zh-Hans":
      """
      他被公司要求进行测试。
      """
    When Humanus checks it with that policy
    Then the rules lane names the policy as not run because "does not provide the built-in check 'passive_voice'"
