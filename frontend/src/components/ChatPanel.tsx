import {
  Card,
  Button,
  Text,
  makeStyles,
  tokens,
} from '@fluentui/react-components'
import {
  MicRegular,
  MicOffRegular,
  DeleteRegular,
  ChartMultipleRegular,
} from '@fluentui/react-icons'
import { Message, Scenario } from '../types'

const useStyles = makeStyles({
  card: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    padding: tokens.spacingVerticalM,
  },
  header: {
    marginBottom: tokens.spacingVerticalM,
    display: 'flex',
    flexDirection: 'column',
    gap: tokens.spacingVerticalXS,
  },
  headerDescription: {
    color: tokens.colorNeutralForeground3,
  },
  messages: {
    flex: 1,
    overflowY: 'auto',
    border: `1px solid ${tokens.colorNeutralStroke1}`,
    borderRadius: tokens.borderRadiusMedium,
    padding: tokens.spacingVerticalM,
    marginBottom: tokens.spacingVerticalM,
  },
  placeholder: {
    height: '100%',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    color: tokens.colorNeutralForeground3,
  },
  message: {
    padding: tokens.spacingVerticalS,
    marginBottom: tokens.spacingVerticalS,
    borderRadius: tokens.borderRadiusMedium,
  },
  userMessage: {
    backgroundColor: tokens.colorBrandBackground2,
    marginLeft: '20%',
  },
  assistantMessage: {
    backgroundColor: tokens.colorNeutralBackground2,
    marginRight: '20%',
  },
  controls: {
    display: 'flex',
    gap: tokens.spacingHorizontalM,
    flexWrap: 'wrap',
  },
  status: {
    display: 'flex',
    alignItems: 'center',
    gap: tokens.spacingHorizontalS,
    marginTop: tokens.spacingVerticalS,
  },
})

interface Props {
  messages: Message[]
  recording: boolean
  connected: boolean
  canAnalyze: boolean
  onToggleRecording: () => void
  onClear: () => void
  onAnalyze: () => void
  scenario?: Scenario | null
}

export function ChatPanel({
  messages,
  recording,
  connected: _connected,
  canAnalyze,
  onToggleRecording,
  onClear,
  onAnalyze,
  scenario,
}: Props) {
  const styles = useStyles()

  return (
    <Card className={styles.card}>
      {scenario && (
        <div className={styles.header}>
          <Text size={500} weight="semibold" block>
            {scenario.name}
          </Text>
          <Text size={300} block className={styles.headerDescription}>
            {scenario.description}
          </Text>
        </div>
      )}

      <div className={styles.messages}>
        {messages.length === 0 ? (
          <div className={styles.placeholder}>
            <Text size={300} weight="semibold">
              Get started
            </Text>
            <Text size={200}>
              Click "Start Recording" to begin the conversation.
            </Text>
          </div>
        ) : (
          <>
            {messages
              .slice()
              .reverse()
              .map(msg => (
                <div
                  key={msg.id}
                  className={`${styles.message} ${
                    msg.role === 'user'
                      ? styles.userMessage
                      : styles.assistantMessage
                  }`}
                >
                  <Text size={300}>{msg.content}</Text>
                </div>
              ))}
          </>
        )}
      </div>

      <div className={styles.controls}>
        <Button
          appearance={recording ? 'primary' : 'secondary'}
          icon={recording ? <MicOffRegular /> : <MicRegular />}
          onClick={onToggleRecording}
        >
          {recording ? 'Stop Recording' : 'Start Recording'}
        </Button>

        <Button appearance="subtle" icon={<DeleteRegular />} onClick={onClear}>
          Clear
        </Button>

        <Button
          appearance="primary"
          icon={<ChartMultipleRegular />}
          onClick={onAnalyze}
          disabled={!canAnalyze}
        >
          Analyze Performance
        </Button>
      </div>
    </Card>
  )
}
