import {
  Dialog,
  DialogSurface,
  DialogTitle,
  DialogBody,
  DialogActions,
  Button,
  Card,
  CardHeader,
  Text,
  ProgressBar,
  Badge,
  makeStyles,
  tokens,
  TabList,
  Tab,
  TabValue,
} from '@fluentui/react-components'
import { Assessment } from '../types'
import { useState } from 'react'

const useStyles = makeStyles({
  dialogBody: {
    padding: tokens.spacingVerticalL,
    display: 'flex',
    flexDirection: 'column',
    gap: tokens.spacingVerticalL,
  },
  headerBar: {
    backgroundColor: tokens.colorNeutralBackground2,
    borderRadius: tokens.borderRadiusLarge,
    padding: tokens.spacingVerticalL,
    display: 'flex',
    flexDirection: 'column',
    gap: tokens.spacingVerticalS,
  },
  scoreRow: {
    display: 'flex',
    alignItems: 'baseline',
    gap: tokens.spacingHorizontalM,
  },
  scoreValue: {
    fontSize: '48px',
    lineHeight: 1,
    fontWeight: 700,
  },
  tabs: {
    // Remove margins to let the parent container handle spacing
  },
  grid: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: tokens.spacingHorizontalL,
  },
  card: {
    padding: tokens.spacingVerticalL,
    height: 'fit-content',
  },
  tabContent: {
    minHeight: '400px',
  },
  sectionTitle: {
    marginBottom: tokens.spacingVerticalM,
    paddingBottom: tokens.spacingVerticalXS,
    borderBottom: `1px solid ${tokens.colorNeutralStroke2}`,
  },
  metric: {
    marginBottom: tokens.spacingVerticalL,
  },
  metricHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: tokens.spacingVerticalS,
  },
  feedbackCard: {
    padding: tokens.spacingVerticalL,
  },
  feedbackSection: {
    marginBottom: tokens.spacingVerticalXL,
  },
  sectionHeader: {
    display: 'flex',
    alignItems: 'center',
    gap: tokens.spacingHorizontalS,
    marginBottom: tokens.spacingVerticalL,
    paddingBottom: tokens.spacingVerticalS,
    borderBottom: `2px solid ${tokens.colorNeutralStroke2}`,
  },
  sectionIcon: {
    fontSize: '24px',
  },
  feedbackGrid: {
    display: 'grid',
    gap: tokens.spacingVerticalM,
  },
  feedbackItem: {
    padding: tokens.spacingVerticalL,
    marginBottom: '0',
    backgroundColor: tokens.colorNeutralBackground1,
    borderRadius: tokens.borderRadiusLarge,
    borderLeft: `4px solid ${tokens.colorBrandBackground}`,
    boxShadow: tokens.shadow4,
    transition: 'all 0.2s ease',
    '&:hover': {
      boxShadow: tokens.shadow8,
      transform: 'translateY(-1px)',
    },
  },
  improvementItem: {
    borderLeftColor: tokens.colorPaletteYellowBackground3,
    backgroundColor: tokens.colorPaletteYellowBackground1,
  },
  strengthItem: {
    borderLeftColor: tokens.colorPaletteGreenBackground3,
    backgroundColor: tokens.colorPaletteGreenBackground1,
  },
  feedbackText: {
    lineHeight: 1.6,
    fontSize: '14px',
  },
  noContent: {
    textAlign: 'center',
    color: tokens.colorNeutralForeground3,
    fontStyle: 'italic',
    padding: tokens.spacingVerticalL,
  },
  wordGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(80px, 1fr))',
    gap: tokens.spacingHorizontalS,
    marginTop: tokens.spacingVerticalM,
  },
})

interface Props {
  open: boolean
  assessment: Assessment | null
  onClose: () => void
}

export function AssessmentPanel({ open, assessment, onClose }: Props) {
  const styles = useStyles()
  const [tab, setTab] = useState<TabValue>('overview')

  if (!assessment) return null

  const getScoreColor = (score: number): 'success' | 'warning' | 'danger' => {
    if (score >= 80) return 'success'
    if (score >= 60) return 'warning'
    return 'danger'
  }

  return (
    <Dialog open={open} onOpenChange={(_, data) => !data.open && onClose()}>
      <DialogSurface
        style={{ maxWidth: '1200px', width: '95vw', maxHeight: '90vh' }}
      >
        <DialogTitle>Performance Assessment</DialogTitle>
        <DialogBody className={styles.dialogBody}>
          {/* Overall Score Section */}
          {assessment.ai_assessment && (
            <div className={styles.headerBar}>
              <Text size={600} weight="semibold">
                Overall Score
              </Text>
              <div className={styles.scoreRow}>
                <span className={styles.scoreValue}>
                  {assessment.ai_assessment.overall_score}
                </span>
                <Badge
                  color={getScoreColor(assessment.ai_assessment.overall_score)}
                  appearance="filled"
                  size="large"
                >
                  {assessment.ai_assessment.overall_score >= 80
                    ? 'Great'
                    : assessment.ai_assessment.overall_score >= 60
                      ? 'Good'
                      : 'Needs Work'}
                </Badge>
              </div>
              <ProgressBar
                value={assessment.ai_assessment.overall_score / 100}
                thickness="large"
              />
            </div>
          )}

          {/* Tabs Section */}
          <TabList
            className={styles.tabs}
            appearance="subtle"
            size="large"
            selectedValue={tab}
            onTabSelect={(_, data) => setTab(data.value)}
          >
            <Tab value="overview">Overview</Tab>
            <Tab value="recommendations">Recommendations</Tab>
            <Tab value="notes">Evaluator Notes</Tab>
          </TabList>

          {/* Content Section */}
          {tab === 'overview' && (
            <div className={styles.grid}>
              {assessment.ai_assessment && (
                <Card className={styles.card}>
                  <CardHeader
                    header={
                      <Text size={500} weight="semibold">
                        🎯 AI Sales Assessment
                      </Text>
                    }
                  />

                  <div className={styles.sectionTitle}>
                    <Text size={400} weight="semibold">
                      Speaking Tone & Style (
                      {assessment.ai_assessment.speaking_tone_style.total}/30)
                    </Text>
                  </div>

                  <div className={styles.metric}>
                    <div className={styles.metricHeader}>
                      <Text size={300}>Professional Tone</Text>
                      <Badge appearance="tint">
                        {
                          assessment.ai_assessment.speaking_tone_style
                            .professional_tone
                        }
                        /10
                      </Badge>
                    </div>
                    <ProgressBar
                      value={
                        assessment.ai_assessment.speaking_tone_style
                          .professional_tone / 10
                      }
                    />
                  </div>

                  <div className={styles.metric}>
                    <div className={styles.metricHeader}>
                      <Text size={300}>Active Listening</Text>
                      <Badge appearance="tint">
                        {
                          assessment.ai_assessment.speaking_tone_style
                            .active_listening
                        }
                        /10
                      </Badge>
                    </div>
                    <ProgressBar
                      value={
                        assessment.ai_assessment.speaking_tone_style
                          .active_listening / 10
                      }
                    />
                  </div>

                  <div className={styles.metric}>
                    <div className={styles.metricHeader}>
                      <Text size={300}>Engagement Quality</Text>
                      <Badge appearance="tint">
                        {
                          assessment.ai_assessment.speaking_tone_style
                            .engagement_quality
                        }
                        /10
                      </Badge>
                    </div>
                    <ProgressBar
                      value={
                        assessment.ai_assessment.speaking_tone_style
                          .engagement_quality / 10
                      }
                    />
                  </div>

                  <div className={styles.sectionTitle}>
                    <Text size={400} weight="semibold">
                      Content Quality (
                      {assessment.ai_assessment.conversation_content.total}/70)
                    </Text>
                  </div>

                  <div className={styles.metric}>
                    <div className={styles.metricHeader}>
                      <Text size={300}>Needs Assessment</Text>
                      <Badge appearance="tint">
                        {
                          assessment.ai_assessment.conversation_content
                            .needs_assessment
                        }
                        /25
                      </Badge>
                    </div>
                    <ProgressBar
                      value={
                        assessment.ai_assessment.conversation_content
                          .needs_assessment / 25
                      }
                    />
                  </div>

                  <div className={styles.metric}>
                    <div className={styles.metricHeader}>
                      <Text size={300}>Value Proposition</Text>
                      <Badge appearance="tint">
                        {
                          assessment.ai_assessment.conversation_content
                            .value_proposition
                        }
                        /25
                      </Badge>
                    </div>
                    <ProgressBar
                      value={
                        assessment.ai_assessment.conversation_content
                          .value_proposition / 25
                      }
                    />
                  </div>

                  <div className={styles.metric}>
                    <div className={styles.metricHeader}>
                      <Text size={300}>Objection Handling</Text>
                      <Badge appearance="tint">
                        {
                          assessment.ai_assessment.conversation_content
                            .objection_handling
                        }
                        /20
                      </Badge>
                    </div>
                    <ProgressBar
                      value={
                        assessment.ai_assessment.conversation_content
                          .objection_handling / 20
                      }
                    />
                  </div>
                </Card>
              )}

              {assessment.pronunciation_assessment && (
                <Card className={styles.card}>
                  <CardHeader
                    header={
                      <Text size={500} weight="semibold">
                        🗣️ Pronunciation Assessment
                      </Text>
                    }
                  />

                  <div className={styles.metric}>
                    <div className={styles.metricHeader}>
                      <Text size={300}>Accuracy</Text>
                      <Badge
                        color={getScoreColor(
                          assessment.pronunciation_assessment.accuracy_score
                        )}
                        appearance="filled"
                      >
                        {assessment.pronunciation_assessment.accuracy_score.toFixed(
                          1
                        )}
                      </Badge>
                    </div>
                    <ProgressBar
                      value={
                        assessment.pronunciation_assessment.accuracy_score / 100
                      }
                    />
                  </div>

                  <div className={styles.metric}>
                    <div className={styles.metricHeader}>
                      <Text size={300}>Fluency</Text>
                      <Badge
                        color={getScoreColor(
                          assessment.pronunciation_assessment.fluency_score
                        )}
                        appearance="filled"
                      >
                        {assessment.pronunciation_assessment.fluency_score.toFixed(
                          1
                        )}
                      </Badge>
                    </div>
                    <ProgressBar
                      value={
                        assessment.pronunciation_assessment.fluency_score / 100
                      }
                    />
                  </div>

                  {assessment.pronunciation_assessment.words && (
                    <>
                      <div className={styles.sectionTitle}>
                        <Text size={400} weight="semibold">
                          Word-Level Analysis
                        </Text>
                      </div>
                      <div className={styles.wordGrid}>
                        {assessment.pronunciation_assessment.words
                          .slice(0, 12)
                          .map((word, i) => (
                            <Badge
                              key={i}
                              color={getScoreColor(word.accuracy)}
                              appearance="tint"
                              size="small"
                            >
                              {word.word} ({word.accuracy}%)
                            </Badge>
                          ))}
                      </div>
                    </>
                  )}
                </Card>
              )}
            </div>
          )}

          {tab === 'recommendations' && assessment.ai_assessment && (
            <Card className={styles.feedbackCard}>
              <CardHeader
                header={
                  <Text size={500} weight="semibold">
                    💡 Improvement Recommendations
                  </Text>
                }
              />

              <div className={styles.feedbackSection}>
                <div className={styles.sectionHeader}>
                  <Text size={500} weight="semibold">
                    Strengths
                  </Text>
                </div>
                {assessment.ai_assessment.strengths.length > 0 ? (
                  <div className={styles.feedbackGrid}>
                    {assessment.ai_assessment.strengths.map((strength, i) => (
                      <div
                        key={i}
                        className={`${styles.feedbackItem} ${styles.strengthItem}`}
                      >
                        <Text className={styles.feedbackText}>{strength}</Text>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className={styles.noContent}>
                    <Text>
                      No specific strengths identified in this session.
                    </Text>
                  </div>
                )}
              </div>

              <div className={styles.feedbackSection}>
                <div className={styles.sectionHeader}>
                  <Text size={500} weight="semibold">
                    Areas for Improvement
                  </Text>
                </div>
                {assessment.ai_assessment.improvements.length > 0 ? (
                  <div className={styles.feedbackGrid}>
                    {assessment.ai_assessment.improvements.map(
                      (improvement, i) => (
                        <div
                          key={i}
                          className={`${styles.feedbackItem} ${styles.improvementItem}`}
                        >
                          <Text className={styles.feedbackText}>
                            {improvement}
                          </Text>
                        </div>
                      )
                    )}
                  </div>
                ) : (
                  <div className={styles.noContent}>
                    <Text>No specific areas for improvement identified.</Text>
                  </div>
                )}
              </div>
            </Card>
          )}

          {tab === 'notes' && (
            <Card className={styles.card}>
              <CardHeader
                header={
                  <Text size={500} weight="semibold">
                    📝 Evaluator Notes
                  </Text>
                }
              />
              <Text size={300} style={{ lineHeight: 1.6 }}>
                {assessment.ai_assessment?.specific_feedback ||
                  'No evaluator notes available.'}
              </Text>
            </Card>
          )}
        </DialogBody>
        <DialogActions>
          <Button appearance="primary" onClick={onClose}>
            Close
          </Button>
        </DialogActions>
      </DialogSurface>
    </Dialog>
  )
}
