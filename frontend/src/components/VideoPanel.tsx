import React from 'react'
import { Card, makeStyles, tokens } from '@fluentui/react-components'

const useStyles = makeStyles({
  card: {
    width: '400px',
    height: '100%',
    padding: tokens.spacingVerticalM,
  },
  videoContainer: {
    width: '100%',
    aspectRatio: '3 / 4',
    backgroundColor: tokens.colorNeutralBackground1,
    borderRadius: tokens.borderRadiusMedium,
    overflow: 'hidden',
    position: 'relative',
  },
  video: {
    width: '100%',
    height: '100%',
    objectFit: 'cover',
  },
})

interface Props {
  videoRef: React.RefObject<HTMLVideoElement>
}

export function VideoPanel({ videoRef }: Props) {
  const styles = useStyles()

  return (
    <Card className={styles.card}>
      <div className={styles.videoContainer}>
        <video ref={videoRef} className={styles.video} autoPlay playsInline />
      </div>
    </Card>
  )
}
