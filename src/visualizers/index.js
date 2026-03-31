const clamp = (value, min, max) => Math.min(Math.max(value, min), max);

const rgba = (hex, alpha = 1) => {
  const normalized = hex.replace('#', '');
  const safe = normalized.length === 3
    ? normalized.split('').map((char) => `${char}${char}`).join('')
    : normalized;

  const red = Number.parseInt(safe.slice(0, 2), 16);
  const green = Number.parseInt(safe.slice(2, 4), 16);
  const blue = Number.parseInt(safe.slice(4, 6), 16);

  return `rgba(${red}, ${green}, ${blue}, ${alpha})`;
};

const averageSlice = (array, start, end) => {
  const boundedStart = clamp(start, 0, array.length - 1);
  const boundedEnd = clamp(end, boundedStart + 1, array.length);
  let total = 0;

  for (let index = boundedStart; index < boundedEnd; index += 1) {
    total += array[index];
  }

  return total / Math.max(1, boundedEnd - boundedStart);
};

const getBands = (frequencyData) => {
  const low = averageSlice(frequencyData, 0, Math.floor(frequencyData.length * 0.08)) / 255;
  const mid = averageSlice(frequencyData, Math.floor(frequencyData.length * 0.08), Math.floor(frequencyData.length * 0.28)) / 255;
  const high = averageSlice(frequencyData, Math.floor(frequencyData.length * 0.28), Math.floor(frequencyData.length * 0.7)) / 255;

  return { low, mid, high };
};

const clearCanvas = (ctx, width, height, transparent) => {
  ctx.clearRect(0, 0, width, height);

  if (!transparent) {
    const gradient = ctx.createLinearGradient(0, 0, width, height);
    gradient.addColorStop(0, '#09090f');
    gradient.addColorStop(1, '#15182a');
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, width, height);
  }
};

const drawGlow = (ctx, x, y, radius, color, alpha) => {
  const gradient = ctx.createRadialGradient(x, y, 0, x, y, radius);
  gradient.addColorStop(0, rgba(color, alpha));
  gradient.addColorStop(1, rgba(color, 0));
  ctx.fillStyle = gradient;
  ctx.beginPath();
  ctx.arc(x, y, radius, 0, Math.PI * 2);
  ctx.fill();
};

const drawBars = (ctx, frame, settings, dimensions) => {
  const { width, height } = dimensions;
  const { frequencyData, level } = frame;
  const barCount = 64;
  const barWidth = width / barCount;

  drawGlow(ctx, width / 2, height * 0.7, 220 + level * 260, settings.primaryColor, 0.16);

  for (let index = 0; index < barCount; index += 1) {
    const start = Math.floor((index / barCount) * frequencyData.length);
    const end = Math.floor(((index + 1) / barCount) * frequencyData.length);
    const value = averageSlice(frequencyData, start, end) / 255;
    const barHeight = Math.max(6, value * height * 0.78 * settings.sensitivity);
    const x = index * barWidth;
    const y = height - barHeight;
    const gradient = ctx.createLinearGradient(0, y, 0, height);
    gradient.addColorStop(0, settings.accentColor);
    gradient.addColorStop(1, settings.primaryColor);
    ctx.fillStyle = gradient;
    ctx.fillRect(x + barWidth * 0.14, y, barWidth * 0.72, barHeight);
  }
};

const drawWaveform = (ctx, frame, settings, dimensions) => {
  const { width, height } = dimensions;
  const { timeDomainData, level } = frame;

  drawGlow(ctx, width / 2, height / 2, 180 + level * 320, settings.accentColor, 0.12);

  ctx.lineWidth = 3;
  ctx.strokeStyle = settings.primaryColor;
  ctx.beginPath();

  for (let index = 0; index < timeDomainData.length; index += 1) {
    const x = (index / (timeDomainData.length - 1)) * width;
    const normalized = (timeDomainData[index] - 128) / 128;
    const y = height / 2 + normalized * height * 0.28 * settings.sensitivity;

    if (index === 0) {
      ctx.moveTo(x, y);
    } else {
      ctx.lineTo(x, y);
    }
  }

  ctx.stroke();
};

const drawRadial = (ctx, frame, settings, dimensions) => {
  const { width, height } = dimensions;
  const { frequencyData, level } = frame;
  const centerX = width / 2;
  const centerY = height / 2;
  const baseRadius = Math.min(width, height) * 0.16;
  const spikeCount = 180;

  drawGlow(ctx, centerX, centerY, 220 + level * 280, settings.primaryColor, 0.18);
  ctx.strokeStyle = settings.accentColor;
  ctx.lineWidth = 2;
  ctx.beginPath();

  for (let index = 0; index <= spikeCount; index += 1) {
    const angle = (index / spikeCount) * Math.PI * 2;
    const frequencyIndex = Math.floor((index / spikeCount) * frequencyData.length);
    const value = frequencyData[frequencyIndex] / 255;
    const radius = baseRadius + value * Math.min(width, height) * 0.26 * settings.sensitivity;
    const x = centerX + Math.cos(angle) * radius;
    const y = centerY + Math.sin(angle) * radius;

    if (index === 0) {
      ctx.moveTo(x, y);
    } else {
      ctx.lineTo(x, y);
    }
  }

  ctx.closePath();
  ctx.stroke();
};

const drawPulse = (ctx, frame, settings, dimensions) => {
  const { width, height } = dimensions;
  const { low, mid, high } = getBands(frame.frequencyData);
  const centerX = width / 2;
  const centerY = height / 2;
  const radius = Math.min(width, height) * (0.13 + low * 0.18 * settings.sensitivity);

  drawGlow(ctx, centerX, centerY, radius * 3.4, settings.primaryColor, 0.14 + low * 0.2);

  ctx.beginPath();
  ctx.fillStyle = rgba(settings.primaryColor, 0.24 + low * 0.32);
  ctx.arc(centerX, centerY, radius, 0, Math.PI * 2);
  ctx.fill();

  ctx.beginPath();
  ctx.lineWidth = 8 + mid * 12;
  ctx.strokeStyle = rgba(settings.accentColor, 0.65 + high * 0.25);
  ctx.arc(centerX, centerY, radius + 20 + high * 30, 0, Math.PI * 2);
  ctx.stroke();
};

const drawSpectrogram = (ctx, frame, settings, dimensions, state) => {
  const { width, height } = dimensions;
  const columns = state.spectrogramColumns;
  const columnWidth = Math.max(1, Math.ceil(width / columns.length));
  const nextColumn = new Uint8Array(96);

  for (let index = 0; index < nextColumn.length; index += 1) {
    const start = Math.floor((index / nextColumn.length) * frame.frequencyData.length);
    const end = Math.floor(((index + 1) / nextColumn.length) * frame.frequencyData.length);
    nextColumn[index] = Math.floor(averageSlice(frame.frequencyData, start, end));
  }

  columns.push(nextColumn);

  while (columns.length > Math.ceil(width / columnWidth)) {
    columns.shift();
  }

  columns.forEach((column, columnIndex) => {
    for (let bandIndex = 0; bandIndex < column.length; bandIndex += 1) {
      const value = column[bandIndex] / 255;
      const x = width - (columns.length - columnIndex) * columnWidth;
      const y = height - ((bandIndex + 1) / column.length) * height;
      ctx.fillStyle = rgba(value > 0.6 ? settings.accentColor : settings.primaryColor, 0.15 + value * 0.85);
      ctx.fillRect(x, y, columnWidth, Math.ceil(height / column.length) + 1);
    }
  });
};

export const VISUALIZER_MODES = {
  bars: {
    label: 'Bars',
    draw: drawBars,
  },
  waveform: {
    label: 'Waveform',
    draw: drawWaveform,
  },
  radial: {
    label: 'Radial',
    draw: drawRadial,
  },
  pulse: {
    label: 'Pulse',
    draw: drawPulse,
  },
  spectrogram: {
    label: 'Spectrogram',
    draw: drawSpectrogram,
  },
};

export const createVisualizerState = () => ({
  spectrogramColumns: [],
});

export const renderVisualizer = (ctx, mode, frame, settings, dimensions, state) => {
  clearCanvas(ctx, dimensions.width, dimensions.height, settings.transparentBackground);

  const visualizer = VISUALIZER_MODES[mode] ?? VISUALIZER_MODES.bars;
  visualizer.draw(ctx, frame, settings, dimensions, state);
};
