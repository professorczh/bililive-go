package danmaku

import (
	"context"
	"encoding/json"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"sync"
	"time"

	"github.com/sirupsen/logrus"

	"github.com/bililive-go/bililive-go/src/configs"
	"github.com/bililive-go/bililive-go/src/recorders/danmaku/douyin"
)

// HeatMetricBucket 热度指标切片（5秒采样周期）
type HeatMetricBucket struct {
	TimeSec    int64 `json:"time_sec"`
	Danmaku    int64 `json:"danmaku"`
	Likes      int64 `json:"likes"`
	TotalLikes int64 `json:"total_likes"`
}

// DouyinDanmakuRecorder 抖音弹幕录制器
type DouyinDanmakuRecorder struct {
	baseRecorder
	roomID      string
	cookies     string
	client      *douyin.DouyinClient
	heatMu      sync.Mutex
	heatBuckets map[int64]*HeatMetricBucket
}

// NewDouyinDanmakuRecorder 创建抖音弹幕录制器
func NewDouyinDanmakuRecorder(roomID, cookies, outputFile string, cfg configs.DanmakuConfig, logger *logrus.Entry) *DouyinDanmakuRecorder {
	return &DouyinDanmakuRecorder{
		baseRecorder: baseRecorder{
			outputFile: outputFile,
			cfg:        cfg,
			logger:     logger,
		},
		roomID:      roomID,
		cookies:     cookies,
		heatBuckets: make(map[int64]*HeatMetricBucket),
	}
}

// Start 开始弹幕录制
func (r *DouyinDanmakuRecorder) Start(ctx context.Context) error {
	r.mu.Lock()
	defer r.mu.Unlock()

	if r.running {
		return nil
	}

	r.startAt = time.Now()

	assWriter, err := NewAssWriter(r.outputFile, r.startAt, r.cfg, "Douyin Danmaku")
	if err != nil {
		return err
	}
	r.assWriter = assWriter

	var onGift func(username, giftName string, num int)
	if r.cfg.RecordDouyinGift != nil && *r.cfg.RecordDouyinGift {
		onGift = func(username, giftName string, num int) {
			r.addGift(time.Now(), username, giftName, num, 0, "")
		}
	}
	r.client = douyin.NewDouyinClient(r.roomID, r.cookies, r.onDanmaku, onGift, r.logger)
	r.client.SetOnLike(r.onLike)

	if err := r.client.Start(ctx); err != nil {
		assWriter.Close()
		return err
	}

	r.running = true
	r.logger.Info("抖音弹幕录制已启动（同时监听弹幕与点赞数据）")

	return nil
}

// Stop 停止弹幕录制
func (r *DouyinDanmakuRecorder) Stop() {
	w := r.stopBase()
	c := r.client
	r.client = nil
	if c != nil {
		c.Stop()
	}
	if w != nil {
		w.Close()
	}
	r.saveHeatFile()
	r.logger.Infof("抖音弹幕录制已停止，共录制 %d 条弹幕", r.GetCount())
}

// onDanmaku 弹幕回调
func (r *DouyinDanmakuRecorder) onDanmaku(username, content string) {
	r.addDanmaku(time.Now(), username, content, 16777215)
	r.recordDanmakuMetric()
}

// onLike 点赞回调
func (r *DouyinDanmakuRecorder) onLike(username string, count int64, total int64) {
	r.recordLikeMetric(count, total)
}

func (r *DouyinDanmakuRecorder) recordDanmakuMetric() {
	if r.startAt.IsZero() {
		return
	}
	sec := int64(time.Since(r.startAt).Seconds())
	bucketSec := (sec / 5) * 5
	r.heatMu.Lock()
	defer r.heatMu.Unlock()
	b, ok := r.heatBuckets[bucketSec]
	if !ok {
		b = &HeatMetricBucket{TimeSec: bucketSec}
		r.heatBuckets[bucketSec] = b
	}
	b.Danmaku++
}

func (r *DouyinDanmakuRecorder) recordLikeMetric(count int64, total int64) {
	if r.startAt.IsZero() {
		return
	}
	sec := int64(time.Since(r.startAt).Seconds())
	bucketSec := (sec / 5) * 5
	r.heatMu.Lock()
	defer r.heatMu.Unlock()
	b, ok := r.heatBuckets[bucketSec]
	if !ok {
		b = &HeatMetricBucket{TimeSec: bucketSec}
		r.heatBuckets[bucketSec] = b
	}
	b.Likes += count
	b.TotalLikes = total
}

func (r *DouyinDanmakuRecorder) saveHeatFile() {
	r.heatMu.Lock()
	defer r.heatMu.Unlock()

	if len(r.heatBuckets) == 0 {
		return
	}

	var list []*HeatMetricBucket
	for _, b := range r.heatBuckets {
		list = append(list, b)
	}
	sort.Slice(list, func(i, j int) bool {
		return list[i].TimeSec < list[j].TimeSec
	})

	heatPath := strings.TrimSuffix(r.outputFile, filepath.Ext(r.outputFile)) + "_heat.json"
	data, err := json.MarshalIndent(list, "", "  ")
	if err != nil {
		r.logger.WithError(err).Warn("序列化 _heat.json 失败")
		return
	}

	if err := os.WriteFile(heatPath, data, 0644); err != nil {
		r.logger.WithError(err).Warnf("保存热度数据失败: %s", heatPath)
		return
	}
	r.logger.Infof("已保存热度指标数据: %s (%d 个时间采样桶)", heatPath, len(list))
}
