package weibolive

import (
	"net/http"
	"net/url"
	"regexp"
	"strings"

	"github.com/bililive-go/bililive-go/src/pkg/utils"
	"github.com/hr3lxphr6j/requests"
	"github.com/tidwall/gjson"

	"github.com/bililive-go/bililive-go/src/live"
	"github.com/bililive-go/bililive-go/src/live/internal"
)

const (
	domain = "weibo.com"
	cnName = "微博直播"

	liveurl = "https://weibo.com/l/!/2/wblive/room/show_pc_live.json?live_id="
)

func init() {
	live.Register(domain, new(builder))
}

type builder struct{}

func (b *builder) Build(url *url.URL) (live.Live, error) {
	return &Live{
		BaseLive: internal.NewBaseLive(url),
	}, nil
}

type Live struct {
	internal.BaseLive
	roomID string
}

func (l *Live) getRoomInfo() ([]byte, error) {
	roomid := ""
	reg := regexp.MustCompile(`(1022|1042152):[0-9]+`)
	if match := reg.FindString(l.Url.String()); match != "" {
		roomid = match
	} else {
		paths := strings.Split(strings.Trim(l.Url.Path, "/"), "/")
		if len(paths) > 0 {
			roomid = paths[len(paths)-1]
		}
	}
	if roomid == "" {
		return nil, live.ErrRoomUrlIncorrect
	}
	l.roomID = roomid

	opts := []requests.RequestOption{
		live.CommonUserAgent,
		requests.Headers(map[string]any{
			"Referer": l.Url.String(),
		}),
	}
	if l.Options.Cookies != nil {
		cookies := l.Options.Cookies.Cookies(l.Url)
		if len(cookies) > 0 {
			cookieKVs := make(map[string]string, len(cookies))
			for _, item := range cookies {
				cookieKVs[item.Name] = item.Value
			}
			opts = append(opts, requests.Cookies(cookieKVs))
		}
	}

	resp, err := l.RequestSession.Get(liveurl+roomid, opts...)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return nil, live.ErrRoomNotExist
	}
	body, err := resp.Bytes()
	if err != nil || gjson.GetBytes(body, "error_code").Int() != 0 {
		return nil, live.ErrRoomNotExist
	}
	return body, nil
}

func (l *Live) GetInfo() (info *live.Info, err error) {
	body, err := l.getRoomInfo()
	if err != nil {
		return nil, live.ErrRoomNotExist
	}
	status := gjson.GetBytes(body, "data.status").Int()
	flvUrl := gjson.GetBytes(body, "data.live_origin_flv_url").String()
	hlsUrl := gjson.GetBytes(body, "data.live_origin_hls_url").String()
	replayUrl := gjson.GetBytes(body, "data.replay_origin_url").String()

	// status == 1 代表正在直播中；status == 3 代表已转为回放
	// 当存在可用的实时流或回放流地址时，判定为处于可录制状态
	isLive := status == 1 || (status == 3 && (replayUrl != "" || flvUrl != "" || hlsUrl != ""))

	info = &live.Info{
		Live:         l,
		HostName:     gjson.GetBytes(body, "data.user.screenName").String(),
		RoomName:     gjson.GetBytes(body, "data.title").String(),
		Status:       isLive,
		CustomLiveId: "weibolive/" + l.roomID,
	}
	return info, nil
}

func (l *Live) GetStreamUrls() (us []*url.URL, err error) {
	body, err := l.getRoomInfo()
	if err != nil {
		return nil, live.ErrRoomNotExist
	}

	streamurl := gjson.GetBytes(body, "data.live_origin_flv_url").String()
	if streamurl == "" {
		streamurl = gjson.GetBytes(body, "data.live_origin_hls_url").String()
	}
	if streamurl == "" {
		streamurl = gjson.GetBytes(body, "data.replay_origin_url").String()
	}
	if streamurl == "" {
		return nil, live.ErrLiveOffline
	}

	queryParams := l.Url.Query()
	quality := queryParams.Get("q")
	if quality != "" && strings.Contains(streamurl, ".flv") {
		targetQuality := "_wb" + quality + "avc.flv"
		reg, err := regexp.Compile(`_wb[\d]+avc\.flv`)
		if err == nil && reg.MatchString(streamurl) {
			streamurl = reg.ReplaceAllString(streamurl, targetQuality)
		} else {
			streamurl = strings.ReplaceAll(streamurl, ".flv", targetQuality)
		}
		l.GetLogger().Info("weibo stream quality fixed: " + streamurl)
	}

	return utils.GenUrls(streamurl)
}

func (l *Live) GetPlatformCNName() string {
	return cnName
}
