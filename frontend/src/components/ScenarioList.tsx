import {
  Card,
  CardHeader,
  Text,
  makeStyles,
  tokens,
  Button,
} from '@fluentui/react-components'
import { Scenario } from '../types'

const useStyles = makeStyles({
  container: {
    display: 'flex',
    flexDirection: 'column',
    gap: tokens.spacingVerticalM,
    width: '100%',
  },
  header: {
    gridColumn: '1 / -1',
  },
  cardsGrid: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: tokens.spacingVerticalM,
    gridColumn: '1 / span 2',
    width: '100%',
    '@media (max-width: 600px)': {
      gridTemplateColumns: '1fr',
    },
  },
  card: {
    cursor: 'pointer',
    transition: 'all 0.2s',
    '&:hover': {
      transform: 'translateY(-2px)',
      boxShadow: tokens.shadow16,
    },
  },
  selected: {
    backgroundColor: tokens.colorBrandBackground2,
  },
  actions: {
    gridColumn: '1 / -1',
    display: 'flex',
    justifyContent: 'flex-end',
    marginTop: tokens.spacingVerticalL,
  },
})

interface Props {
  scenarios: Scenario[]
  selectedScenario: string | null
  onSelect: (id: string) => void
  onStart: () => void
}

export function ScenarioList({
  scenarios,
  selectedScenario,
  onSelect,
  onStart,
}: Props) {
  const styles = useStyles()

  return (
    <>
      <Text className={styles.header} size={500} weight="semibold">
        Select Training Scenario
      </Text>
      <div className={styles.cardsGrid}>
        {scenarios.map(scenario => (
          <Card
            key={scenario.id}
            className={`${styles.card} ${selectedScenario === scenario.id ? styles.selected : ''}`}
            onClick={() => onSelect(scenario.id)}
          >
            <CardHeader
              header={<Text weight="semibold">{scenario.name}</Text>}
              description={<Text size={200}>{scenario.description}</Text>}
            />
          </Card>
        ))}
      </div>
      <div className={styles.actions}>
        <Button
          appearance="primary"
          disabled={!selectedScenario}
          onClick={onStart}
          size="large"
        >
          Start Training
        </Button>
      </div>
    </>
  )
}
